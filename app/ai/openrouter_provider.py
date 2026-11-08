import json
import asyncio
import time
import re
from typing import Optional, List, Tuple, Dict, Any
import httpx
from app.config.settings import settings
from app.ai.base_provider import BaseLLMProvider, AISponsorMatchResult
from app.utils.logger import logger

SPONSOR_EVAL_PROMPT = """
You are a senior brand partnership executive and sponsorship matching AI.
Evaluate whether the following corporate sponsor/brand is a strong, valuable match for the submitted Event Proposal.

Sponsor Profile:
- Company / Brand: {sponsor_name}
- Industry / Category: {category}
- Known Target Demographics: {target_demographics}
- Sponsor Description: {description}

Event Proposal Context:
{proposal_text}

Evaluation Dimensions:
1. Demographic & Audience Overlap: Does this brand market to the event's attendee profile?
2. Brand Value Alignment: Does sponsoring this event benefit their CSR, marketing, or recruitment goals?
3. Strategic ROI & Practical Fit: Does the brand typically provide cash, in-kind products, prizes, or tech resources?

You MUST return ONLY a valid JSON object with this exact structure:
{{
  "recommended": true/false,
  "score": 0-100 (integer representing match percentage),
  "reason": ["bullet reason 1", "bullet reason 2"],
  "value_proposition_angle": "The sharp strategic angle on why this sponsor should sponsor this specific event (e.g. brand awareness among 500 CS students)",
  "suggested_tier": "Suggested sponsorship tier (e.g. Platinum, Gold, In-Kind Partner, Media Partner)",
  "matched_demographics": ["demographic 1", "demographic 2"],
  "summary": "Concise summary in Indonesian or English explaining why this sponsor is a great fit.",
  "priority": "low" or "medium" or "high"
}}
"""

PROPOSAL_PARSER_PROMPT = """
You are an expert event producer and sponsorship consultant.
Analyze the following Event / Project Proposal text and extract key metadata into structured sponsorship criteria.

Proposal Text:
{proposal_text}

You MUST return ONLY a valid JSON object with this exact structure:
{{
  "title": "Clear event name/title",
  "event_type": "Hackathon / Tech Conference / Campus Festival / Competition / Workshop / Charity / Esports",
  "target_audience": "Concise description of who attends (e.g. 500+ university CS students, age 18-24)",
  "expected_attendees": "Estimated count (e.g. 500-1000 participants)",
  "location": "City or Virtual (e.g. Jakarta, Indonesia or Online)",
  "event_date": "Target date or timeline",
  "requested_budget": "Estimated budget or goal (e.g. Rp 50.000.000 / $3,500)",
  "sponsorship_tiers": {{
    "Platinum": "Rp 25.000.000",
    "Gold": "Rp 15.000.000",
    "Silver": "Rp 5.000.000",
    "In-Kind": "Product sampling / tools"
  }},
  "detected_topics": ["Topic 1", "Topic 2", "Topic 3"],
  "recommended_sponsor_categories": ["Tech", "FMCG", "Fintech", "Beverage"],
  "search_keywords": ["search phrase 1", "search phrase 2", "search phrase 3"],
  "summary": "2-3 sentences summarizing the event concept and the high-value opportunity for prospective sponsors."
}}
"""

PITCH_WRITER_PROMPT = """
You are a master corporate partnership director and professional copywriter.
Draft a high-converting, polite, and persuasive cold sponsorship outreach email for the event below.
Address the brand's partnership/marketing/CSR manager.
Emphasize value ROI (audience reach, brand visibility, community goodwill) and mention that the full proposal deck is attached.

Brand / Company: {sponsor_name}
Target Tier: {suggested_tier}
Strategic Value Angle: {pitch_angle}
Event Proposal Title: {proposal_title}
Event Summary: {proposal_summary}
Event Timeline: {event_date}

Format instructions:
Return ONLY a valid JSON object:
{{
  "subject": "Compelling, professional email subject line (under 60 chars)",
  "body": "The full email body formatted professionally with greeting, intro, hook, benefits, CTA, and closing."
}}
"""

class OpenRouterProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self.api_key = settings.OPENROUTER_API_KEY
        self.api_url = settings.OPENROUTER_API_URL
        self.primary_model = settings.PRIMARY_MODEL
        self.fallback_models = settings.fallback_models_list

    def _is_mock(self) -> bool:
        return not self.api_key or self.api_key in ["mock_key", "your_openrouter_api_key_here", "none"]

    async def verify_connectivity(self) -> Tuple[bool, str, int]:
        if self._is_mock():
            return True, "Mock Mode (Heuristic Rule Engine Active)", 5
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.primary_model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 5
                    }
                )
                latency = int((time.time() - start) * 1000)
                if res.status_code == 200:
                    return True, "Connected", latency
                return False, f"HTTP {res.status_code}: {res.text[:100]}", latency
        except Exception as e:
            return False, str(e), int((time.time() - start) * 1000)

    async def _call_llm(self, prompt: str, system: Optional[str] = None) -> Optional[str]:
        if self._is_mock():
            return None

        models_to_try = [self.primary_model] + self.fallback_models
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/sponsor-finder",
            "X-Title": "Sponsor Finder Multi-Agent"
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for model in models_to_try:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        self.api_url,
                        headers=headers,
                        json={
                            "model": model,
                            "messages": messages,
                            "temperature": 0.2,
                            "response_format": {"type": "json_object"}
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        logger.warning(f"LLM model {model} returned HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"Error calling model {model}: {e}")
        return None

    def _clean_json(self, text: str) -> Dict[str, Any]:
        """Strip markdown ticks and parse JSON safely."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        return json.loads(cleaned)

    async def evaluate_sponsor_fit(
        self,
        sponsor_name: str,
        category: str,
        description: str,
        target_demographics: str,
        proposal_text: str
    ) -> AISponsorMatchResult:
        prompt = SPONSOR_EVAL_PROMPT.format(
            sponsor_name=sponsor_name,
            category=category or "General",
            target_demographics=target_demographics or "General Youth / Public",
            description=description or "",
            proposal_text=proposal_text[:3500]
        )

        content = await self._call_llm(prompt)
        if content:
            try:
                parsed = self._clean_json(content)
                return AISponsorMatchResult(
                    recommended=bool(parsed.get("recommended", False)),
                    score=int(parsed.get("score", 50)),
                    reason=parsed.get("reason", []),
                    value_proposition_angle=str(parsed.get("value_proposition_angle", "")),
                    suggested_tier=str(parsed.get("suggested_tier", "Gold Sponsor")),
                    matched_demographics=parsed.get("matched_demographics", []),
                    summary=str(parsed.get("summary", "")),
                    priority=str(parsed.get("priority", "medium"))
                )
            except Exception as e:
                logger.error(f"Failed to parse LLM sponsor evaluation: {e}")

        # Deterministic Heuristic Fallback
        return self._heuristic_evaluate(sponsor_name, category, description, target_demographics, proposal_text)

    def _heuristic_evaluate(
        self,
        sponsor_name: str,
        category: str,
        description: str,
        target_demographics: str,
        proposal_text: str
    ) -> AISponsorMatchResult:
        prop_lower = proposal_text.lower()
        score = 50
        matched = []
        reasons = []

        # Check demographic keywords
        demo_keywords = ["student", "mahasiswa", "developer", "coding", "gamer", "esports", "youth", "gen-z", "wanita", "sekolah", "smk", "komunitas", "tech", "ai"]
        for kw in demo_keywords:
            if kw in (target_demographics or "").lower() and kw in prop_lower:
                score += 8
                matched.append(kw)

        # Category bonuses
        cat_lower = (category or "").lower()
        if "tech" in cat_lower and any(w in prop_lower for w in ["hackathon", "coding", "software", "ai", "robotics"]):
            score += 20
            reasons.append("Kesesuaian tinggi antara industri teknologi/software dengan tema teknis kegiatan.")
        elif "fmcg" in cat_lower or "beverage" in cat_lower or "food" in cat_lower:
            if any(w in prop_lower for w in ["festival", "expo", "peserta", "bazaar", "konser", "lomba", "turnamen"]):
                score += 18
                reasons.append("Tingginya potensi aktivasi sampling produk dan konsumsi peserta di lokasi event.")
        elif "gaming" in cat_lower and any(w in prop_lower for w in ["esports", "game", "gaming", "turnamen"]):
            score += 25
            reasons.append("Sangat relevan untuk promosi lini produk gaming hardware dan co-branding turnamen.")
        elif "bank" in cat_lower or "fintech" in cat_lower:
            if any(w in prop_lower for w in ["seminar", "bisnis", "financial", "qris", "cashless", "mahasiswa"]):
                score += 15
                reasons.append("Peluang strategis untuk edukasi literasi keuangan dan aktivasi transaksi non-tunai.")

        score = min(max(score, 35), 96)
        recommended = score >= settings.SCORE_THRESHOLD

        angle = f"Menghubungkan {sponsor_name} langsung dengan komunitas peserta aktif untuk memperkuat brand recall dan penetrasi pasar."
        summary = f"Evaluasi kecocokan {sponsor_name} dengan proposal menghasilkan skor {score}%. {'Sangat direkomendasikan untuk dihubungi.' if recommended else 'Cukup relevan sebagai opsi pendukung.'}"

        return AISponsorMatchResult(
            recommended=recommended,
            score=score,
            reason=reasons or ["Target audiens memiliki irisan yang memadai dengan profil konsumen brand."],
            value_proposition_angle=angle,
            suggested_tier="Gold / In-Kind Partner" if score >= 80 else "Silver Sponsor",
            matched_demographics=matched or ["Pelajar/Mahasiswa", "Komunitas"],
            summary=summary,
            priority="high" if score >= 80 else "medium"
        )

    async def analyze_proposal_document(self, proposal_text: str) -> Dict[str, Any]:
        prompt = PROPOSAL_PARSER_PROMPT.format(proposal_text=proposal_text[:4000])
        content = await self._call_llm(prompt)
        if content:
            try:
                return self._clean_json(content)
            except Exception as e:
                logger.error(f"Error parsing proposal JSON: {e}")

        # Heuristic fallback parser
        return self._heuristic_parse_proposal(proposal_text)

    def _heuristic_parse_proposal(self, text: str) -> Dict[str, Any]:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        title = lines[0][:80] if lines else "Event Sponsorship Proposal"
        
        lower = text.lower()
        event_type = "Conference / Event"
        if "hackathon" in lower:
            event_type = "Hackathon & Tech Competition"
        elif "esports" in lower or "turnamen" in lower:
            event_type = "Esports Tournament"
        elif "seminar" in lower or "webinar" in lower:
            event_type = "Educational Seminar"
        elif "festival" in lower or "konser" in lower:
            event_type = "Festival & Cultural Night"
        elif "lomba" in lower or "kompetisi" in lower:
            event_type = "Competition"

        topics = []
        for kw in ["Technology", "Software", "AI", "Business", "Health", "Youth Empowerment", "Environment", "Design"]:
            if kw.lower() in lower:
                topics.append(kw)

        return {
            "title": title,
            "event_type": event_type,
            "target_audience": "Pelajar, Mahasiswa, Komunitas Muda & Praktisi",
            "expected_attendees": "300 - 1.000 Peserta",
            "location": "Jakarta / Hybrid",
            "event_date": "Upcoming Q3/Q4",
            "requested_budget": "Rp 25.000.000 - Rp 50.000.000",
            "sponsorship_tiers": {
                "Platinum": "Rp 25.000.000",
                "Gold": "Rp 15.000.000",
                "Silver": "Rp 7.500.000",
                "In-Kind / Media Partner": "Free / Barter"
            },
            "detected_topics": topics or ["Pemuda & Pendidikan", "Inovasi"],
            "recommended_sponsor_categories": ["Tech", "FMCG / Beverage", "Banking", "Telco"],
            "search_keywords": ["sponsor event mahasiswa", "program csr brand indonesia", "tech sponsorship hackathon"],
            "summary": f"Proposal kegiatan '{title}' ({event_type}) yang berfokus pada keterlibatan audiens muda dan potensi kolaborasi brand."
        }

    async def write_sponsorship_pitch(
        self,
        sponsor_name: str,
        contact_person: Optional[str],
        proposal_title: str,
        proposal_summary: str,
        suggested_tier: Optional[str],
        pitch_angle: str,
        event_date: Optional[str] = None
    ) -> Tuple[str, str]:
        prompt = PITCH_WRITER_PROMPT.format(
            sponsor_name=sponsor_name,
            suggested_tier=suggested_tier or "Sponsor Partner",
            pitch_angle=pitch_angle or "Meningkatkan brand visibility di kalangan generasi muda.",
            proposal_title=proposal_title,
            proposal_summary=proposal_summary,
            event_date=event_date or "Mendatang"
        )

        content = await self._call_llm(prompt)
        if content:
            try:
                parsed = self._clean_json(content)
                return parsed.get("subject", f"Peluang Kemitraan & Sponsorship: {proposal_title}"), parsed.get("body", "")
            except Exception as e:
                logger.error(f"Error parsing pitch email JSON: {e}")

        # Fallback template
        recipient = contact_person or f"Tim Partnership & Brand {sponsor_name}"
        subject = f"Peluang Kolaborasi & Sponsorship - {proposal_title}"
        body = f"""Kepada Yth.
{recipient}
di Tempat

Dengan hormat,

Perkenalkan, kami dari panitia penyelenggara kegiatan "{proposal_title}". Kami menghubungi pihak {sponsor_name} karena melihat keselarasan luar biasa antara visi brand Anda dengan fokus kegiatan kami ({proposal_summary}).

Melalui kegiatan ini, kami membuka kesempatan kemitraan strategis ({suggested_tier or 'Sponsor Partner'}) yang dirancang untuk:
- {pitch_angle}
- Memberikan eksposur maksimal langsung kepada target audiens potensial brand Anda.
- Aktivasi interaktif (booth, sampling produk, atau slot pembicara kehormatan).

Bersama surat ini, kami lampirkan dokumen lengkap Proposal Sponsorship yang memuat rincian paket kemitraan, proyeksi audiens, serta rincian kegiatan.

Kami sangat menghargai kesempatan untuk mendiskusikan peluang kolaborasi ini lebih lanjut pada jadwal yang fleksibel bagi Bapak/Ibu.

Terima kasih atas perhatian dan kerja sama yang baik.

Hormat kami,
Panitia Pelaksana {proposal_title}
Email: [Email Kontak]
WhatsApp: [Nomor Kontak]
"""
        return subject, body
