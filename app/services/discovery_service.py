import re
import urllib.parse
from typing import List, Set, Optional, Dict, Any
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.config.settings import settings
from app.database.db import async_session_maker
from app.database.models import Sponsor
from app.utils.contact_parser import extract_clean_emails
from app.utils.logger import logger

SPONSOR_SEARCH_QUERIES = [
    "proposal sponsorship diterima email perusahaan indonesia",
    "program CSR pt csr sponsorship event kampus",
    "brand partnership youth event sponsorship contact email",
    "hackathon developer grant community sponsorship email",
    "sponsorship proposal submission brand marketing email",
    "panduan pengajuan sponsorship event mahasiswa indonesia"
]

EXCLUDED_DOMAINS = {
    "google.com", "youtube.com", "facebook.com", "instagram.com", "twitter.com",
    "linkedin.com", "indeed.com", "glints.com", "jobstreet.co.id", "wikipedia.org",
    "github.com", "medium.com", "reddit.com", "pinterest.com", "tiktok.com"
}

class SponsorDiscoveryEngine:
    def __init__(self) -> None:
        self.headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    def _extract_domain(self, url: str) -> Optional[str]:
        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.netloc:
                return None
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            if netloc in EXCLUDED_DOMAINS or any(netloc.endswith(f".{d}") for d in EXCLUDED_DOMAINS):
                return None
            return f"{parsed.scheme}://{netloc}"
        except Exception:
            return None

    def _derive_company_name(self, domain: str) -> str:
        parsed = urllib.parse.urlparse(domain)
        host = parsed.netloc
        if host.startswith("www."):
            host = host[4:]
        clean = host.split(".")[0].replace("-", " ").replace("_", " ")
        return clean.title()

    async def search_duckduckgo(self, query: str, max_results: int = 10) -> List[str]:
        """Perform search query to find relevant company partnership landing pages."""
        results = []
        try:
            encoded = urllib.parse.quote_plus(query)
            search_url = f"https://html.duckduckgo.com/html/?q={encoded}"
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=self.headers) as client:
                res = await client.get(search_url)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    for a in soup.select("a.result__url"):
                        raw_href = a.get("href", "")
                        # Duckduckgo redirects look like /l/?kh=-1&uddg=https%3A%2F%2F...
                        if "uddg=" in raw_href:
                            match = re.search(r"uddg=([^&]+)", raw_href)
                            if match:
                                target = urllib.parse.unquote(match.group(1))
                                domain = self._extract_domain(target)
                                if domain and domain not in results:
                                    results.append(domain)
                        else:
                            domain = self._extract_domain(raw_href)
                            if domain and domain not in results:
                                results.append(domain)
                        if len(results) >= max_results:
                            break
        except Exception as e:
            logger.warning(f"Search query '{query}' failed: {e}")
        return results

    async def crawl_sponsor_contact_info(self, domain: str) -> Dict[str, Any]:
        """Visit target domain's home and contact/partnership pages to extract email and description."""
        contacts = {
            "email": None,
            "partnership_url": None,
            "description": None
        }
        target_paths = ["", "/contact", "/partnership", "/sponsorship", "/csr", "/hubungi-kami", "/about"]

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=self.headers) as client:
            for path in target_paths:
                url = f"{domain.rstrip('/')}{path}"
                try:
                    res = await client.get(url)
                    if res.status_code == 200:
                        text = res.text
                        emails = extract_clean_emails(text)
                        if emails and not contacts["email"]:
                            contacts["email"] = emails[0]
                            contacts["partnership_url"] = url

                        if not contacts["description"]:
                            soup = BeautifulSoup(text, "html.parser")
                            meta_desc = soup.find("meta", attrs={"name": "description"})
                            if meta_desc and meta_desc.get("content"):
                                contacts["description"] = meta_desc["content"][:300]
                            elif soup.title and soup.title.string:
                                contacts["description"] = soup.title.string[:200]

                        if contacts["email"] and contacts["description"]:
                            break
                except Exception:
                    continue

        return contacts

    async def discover_new_sponsors(self, max_new: int = 5) -> int:
        """Run discovery across queries and save new potential sponsors into the database."""
        discovered_count = 0
        domains_found: Set[str] = set()

        for q in SPONSOR_SEARCH_QUERIES[:3]:
            domains = await self.search_duckduckgo(q, max_results=6)
            for d in domains:
                domains_found.add(d)

        async with async_session_maker() as session:
            for domain in domains_found:
                if discovered_count >= max_new:
                    break

                comp_name = self._derive_company_name(domain)
                stmt = select(Sponsor).where(Sponsor.name.ilike(comp_name))
                res = await session.execute(stmt)
                if res.scalar_one_or_none():
                    continue

                contact_info = await self.crawl_sponsor_contact_info(domain)
                region = "Indonesia" if domain.endswith(".id") or "indonesia" in comp_name.lower() else "Global"

                sponsor = Sponsor(
                    name=comp_name,
                    website=domain,
                    partnership_url=contact_info.get("partnership_url") or domain,
                    contact_email=contact_info.get("email"),
                    email_source="web_discovery",
                    category="Corporate & Brand",
                    region=region,
                    description=contact_info.get("description") or f"Corporate enterprise and brand based at {domain}",
                    typical_sponsorship="Event Sponsorship & Community Partnership",
                    is_discovered=True,
                    status="active"
                )
                session.add(sponsor)
                await session.commit()
                discovered_count += 1
                logger.info(f"Discovered new corporate sponsor: {comp_name} ({domain}) | Contact: {contact_info.get('email')}")

        return discovered_count

discovery_engine = SponsorDiscoveryEngine()
