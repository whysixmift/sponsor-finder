import re
import urllib.parse
from typing import List, Optional

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
)

# Common generic / noise emails to skip
IGNORED_EMAIL_DOMAINS = {
    "example.com", "domain.com", "yourdomain.com", "email.com",
    "wixpress.com", "sentry.io", "github.com", "google.com"
}

def extract_clean_emails(text: str) -> List[str]:
    """Extract valid emails, prioritizing sponsorship, partnership, csr, and marketing contacts."""
    if not text:
        return []
    
    raw_emails = EMAIL_REGEX.findall(text)
    clean_emails = []
    seen = set()

    # Priority keywords for sponsors
    priority_keywords = ["sponsor", "partnership", "partner", "csr", "pr", "marketing", "event", "community", "collaboration", "info", "contact"]

    sorted_raw = sorted(
        raw_emails,
        key=lambda em: any(kw in em.lower() for kw in priority_keywords),
        reverse=True
    )

    for email in sorted_raw:
        em_lower = email.lower().strip(".")
        domain = em_lower.split("@")[-1] if "@" in em_lower else ""
        if domain in IGNORED_EMAIL_DOMAINS:
            continue
        # Skip image file extensions that might be matched
        if any(em_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"]):
            continue
        if em_lower not in seen:
            seen.add(em_lower)
            clean_emails.append(em_lower)

    return clean_emails

def extract_whatsapp_number(text: str) -> Optional[str]:
    """Extract phone numbers suitable for Indonesian or International WhatsApp outreach."""
    if not text:
        return None
    patterns = [
        r"(?:https?:\/\/wa\.me\/|https?:\/\/api\.whatsapp\.com\/send\?phone=)(\d+)",
        r"(?:\+?62|08)[1-9][0-9]{7,11}",
        r"\+?[1-9]\d{1,14}"
    ]
    for pat in patterns:
        match = re.search(pat, text)
        if match:
            raw = match.group(0)
            digits = re.sub(r"\D", "", raw)
            if digits.startswith("08"):
                digits = "628" + digits[2:]
            if len(digits) >= 10:
                return digits
    return None

def build_whatsapp_outreach_url(phone: str, text: str) -> str:
    encoded_text = urllib.parse.quote(text)
    return f"https://wa.me/{phone}?text={encoded_text}"

def build_linkedin_search_url(company_name: str, role: str = "Partnership Manager") -> str:
    query = f"{company_name} {role}"
    return f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(query)}"
