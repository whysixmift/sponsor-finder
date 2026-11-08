from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.base_agent import BaseAgent
from app.database.models import ProposalProfile
from app.services.proposal_service import proposal_service
from app.utils.logger import logger

class ProposalAgent(BaseAgent):
    """Autonomous agent for proposal ingestion, physical file persistence, text extraction, and event profiling."""

    def __init__(self) -> None:
        super().__init__(
            agent_name="ProposalAgent",
            feature_description="Event Proposal Document Ingestion, Physical Attachment Storage & Profiler"
        )

    async def ingest_proposal(
        self,
        session: AsyncSession,
        user_id: int,
        filename: str,
        file_bytes: bytes
    ) -> ProposalProfile:
        start = self.mark_start()
        try:
            profile = await proposal_service.save_proposal(session, user_id, filename, file_bytes)
            self.mark_success(start)
            return profile
        except Exception as e:
            self.mark_failure(start, e)
            raise e

    async def get_user_proposal(self, session: AsyncSession, user_id: int) -> Optional[ProposalProfile]:
        start = self.mark_start()
        try:
            profile = await proposal_service.get_user_proposal(session, user_id)
            self.mark_success(start)
            return profile
        except Exception as e:
            self.mark_failure(start, e)
            return None

proposal_agent = ProposalAgent()
