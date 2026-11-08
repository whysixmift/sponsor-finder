from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.base_agent import BaseAgent
from app.database.models import EmailQueue
from app.services.email_service import email_service
from app.utils.logger import logger

class EmailDraftingAgent(BaseAgent):
    """Autonomous agent for drafting personalized sponsorship pitch letters with proposal attachments."""

    def __init__(self) -> None:
        super().__init__(
            agent_name="EmailDraftingAgent",
            feature_description="AI Sponsorship Pitch & Cold Email Drafting Engine"
        )

    async def create_draft(
        self,
        session: AsyncSession,
        user_id: int,
        sponsor_id: int,
        suggested_tier: Optional[str] = None,
        pitch_angle: Optional[str] = None
    ) -> EmailQueue:
        start = self.mark_start()
        try:
            draft = await email_service.draft_sponsorship_email(
                session=session,
                user_id=user_id,
                sponsor_id=sponsor_id,
                suggested_tier=suggested_tier,
                pitch_angle=pitch_angle
            )
            self.mark_success(start)
            return draft
        except Exception as e:
            self.mark_failure(start, e)
            raise e

email_drafting_agent = EmailDraftingAgent()
