from app.agents.base_agent import BaseAgent
from app.services.discovery_service import discovery_engine
from app.utils.logger import logger

class SponsorDiscoveryAgent(BaseAgent):
    """Autonomous agent for discovering new brands, corporate sponsors, and partnership pages via web scraping."""

    def __init__(self) -> None:
        super().__init__(
            agent_name="SponsorDiscoveryAgent",
            feature_description="Corporate Sponsor & Brand Partnership Web Discovery Engine"
        )

    async def run_discovery(self, limit: int = 5) -> int:
        start = self.mark_start()
        try:
            count = await discovery_engine.discover_new_sponsors(max_new=limit)
            self.mark_success(start)
            return count
        except Exception as e:
            self.mark_failure(start, e)
            return 0

sponsor_discovery_agent = SponsorDiscoveryAgent()
