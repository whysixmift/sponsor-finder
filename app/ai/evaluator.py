from typing import Tuple, Dict, Any, Optional
from app.ai.openrouter_provider import OpenRouterProvider
from app.ai.base_provider import AISponsorMatchResult

class Evaluator:
    def __init__(self) -> None:
        self.provider = OpenRouterProvider()

    async def verify_connectivity(self) -> Tuple[bool, str, int]:
        return await self.provider.verify_connectivity()

    async def evaluate_sponsor_fit(
        self,
        sponsor_name: str,
        category: str,
        description: str,
        target_demographics: str,
        proposal_text: str
    ) -> AISponsorMatchResult:
        return await self.provider.evaluate_sponsor_fit(
            sponsor_name=sponsor_name,
            category=category,
            description=description,
            target_demographics=target_demographics,
            proposal_text=proposal_text
        )

    async def analyze_proposal_document(self, proposal_text: str) -> Dict[str, Any]:
        return await self.provider.analyze_proposal_document(proposal_text)

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
        return await self.provider.write_sponsorship_pitch(
            sponsor_name=sponsor_name,
            contact_person=contact_person,
            proposal_title=proposal_title,
            proposal_summary=proposal_summary,
            suggested_tier=suggested_tier,
            pitch_angle=pitch_angle,
            event_date=event_date
        )

evaluator = Evaluator()
