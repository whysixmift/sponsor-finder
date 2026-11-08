from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Dict, Any
from pydantic import BaseModel, Field

class AISponsorMatchResult(BaseModel):
    recommended: bool = Field(default=False)
    score: int = Field(default=0, ge=0, le=100)
    reason: List[str] = Field(default_factory=list)
    value_proposition_angle: str = Field(default="")
    suggested_tier: Optional[str] = Field(default="Sponsor Partner")
    matched_demographics: List[str] = Field(default_factory=list)
    summary: str = Field(default="")
    priority: Optional[str] = Field(default="medium")

class BaseLLMProvider(ABC):
    """Abstract base class for Sponsor Matching and Pitch Generation."""

    @abstractmethod
    async def verify_connectivity(self) -> Tuple[bool, str, int]:
        """Verify API credentials, latency, and model availability.
        Returns:
            Tuple[success: bool, status_message: str, latency_ms: int]
        """
        pass

    @abstractmethod
    async def evaluate_sponsor_fit(
        self,
        sponsor_name: str,
        category: str,
        description: str,
        target_demographics: str,
        proposal_text: str
    ) -> AISponsorMatchResult:
        """Evaluate how well a brand/sponsor aligns with the submitted event proposal."""
        pass

    @abstractmethod
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
        """Draft a tailored, persuasive cold sponsorship proposal email.
        Returns:
            Tuple[subject: str, email_body: str]
        """
        pass

    @abstractmethod
    async def analyze_proposal_document(self, proposal_text: str) -> Dict[str, Any]:
        """Extract event demographics, budget tiers, topics, and ideal sponsor search queries."""
        pass
