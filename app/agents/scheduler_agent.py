import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.agents.base_agent import BaseAgent
from app.config.settings import settings
from app.agents.sponsor_discovery_agent import sponsor_discovery_agent
from app.utils.logger import logger

class SchedulerAgent(BaseAgent):
    """Autonomous agent orchestrating periodic background tasks and discovery pipelines."""

    def __init__(self) -> None:
        super().__init__(
            agent_name="SchedulerAgent",
            feature_description="Async Periodic Pipeline & Maintenance Scheduler"
        )
        self.scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)

    def start_scheduler(self) -> None:
        if not self.scheduler.running:
            self.scheduler.add_job(
                self._run_periodic_discovery,
                "interval",
                minutes=settings.CHECK_INTERVAL_MINUTES,
                id="sponsor_discovery_job",
                replace_existing=True
            )
            self.scheduler.start()
            logger.info(f"SchedulerAgent started with interval {settings.CHECK_INTERVAL_MINUTES} minutes.")

    async def _run_periodic_discovery(self) -> None:
        start = self.mark_start()
        try:
            logger.info("SchedulerAgent running periodic web sponsor discovery...")
            count = await sponsor_discovery_agent.run_discovery(limit=3)
            logger.info(f"SchedulerAgent completed discovery run. Added {count} new sponsors.")
            self.mark_success(start)
        except Exception as e:
            self.mark_failure(start, e)

scheduler_agent = SchedulerAgent()
