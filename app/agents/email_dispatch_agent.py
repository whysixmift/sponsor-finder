from sqlalchemy.ext.asyncio import AsyncSession
from app.agents.base_agent import BaseAgent
from app.services.email_service import email_service
from app.utils.logger import logger

class EmailDispatchAgent(BaseAgent):
    """Autonomous agent for multi-protocol cold email sending (Gmail API + SMTP)."""

    def __init__(self) -> None:
        super().__init__(
            agent_name="EmailDispatchAgent",
            feature_description="Multi-Protocol Mailer (Gmail API OAuth2 + Encrypted SMTP)"
        )

    async def send_email(self, session: AsyncSession, email_id: int) -> bool:
        start = self.mark_start()
        try:
            res = await email_service.dispatch_email(session, email_id)
            self.mark_success(start)
            return res
        except Exception as e:
            self.mark_failure(start, e)
            raise e

email_dispatch_agent = EmailDispatchAgent()
