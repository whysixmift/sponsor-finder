from typing import Optional
from sqlalchemy import select, or_, and_
from app.agents.base_agent import BaseAgent
from app.config.settings import settings
from app.database.db import async_session_maker
from app.database.models import UserWhitelist
from app.utils.logger import logger

class AccessControlAgent(BaseAgent):
    """Autonomous agent verifying SaaS access whitelist by Telegram User ID or Username."""

    def __init__(self) -> None:
        super().__init__(
            agent_name="AccessControlAgent",
            feature_description="SaaS User Whitelist & Authorization Gatekeeper"
        )

    async def is_allowed(self, user_id: int, username: Optional[str] = None) -> bool:
        start = self.mark_start()
        try:
            # 1. Superadmin bypass
            if user_id == settings.TELEGRAM_ADMIN_ID:
                self.mark_success(start)
                return True

            async with async_session_maker() as session:
                clean_username = username.lstrip("@").lower() if username else None
                conditions = [
                    and_(UserWhitelist.telegram_id == user_id, UserWhitelist.is_active == True)
                ]
                if clean_username:
                    conditions.append(
                        and_(UserWhitelist.username.ilike(clean_username), UserWhitelist.is_active == True)
                    )

                stmt = select(UserWhitelist).where(or_(*conditions))
                res = await session.execute(stmt)
                user = res.scalar_one_or_none()

                allowed = user is not None
                self.mark_success(start)
                return allowed

        except Exception as e:
            self.mark_failure(start, e)
            return False

access_control_agent = AccessControlAgent()
