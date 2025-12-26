from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig

from .service import GitHubService


class GitHubScheduler:
    """GitHub 定时监控调度器"""

    def __init__(self, config: AstrBotConfig, service: GitHubService):
        self.config = config
        self.service = service
        self.scheduler = AsyncIOScheduler()
        self.started = False

    def start(self):
        if self.started:
            return

        self.scheduler.add_job(
            self.service.check_repositories,
            trigger=IntervalTrigger(seconds=self.config["interval"]),
            id="github_star_monitor",
            replace_existing=True,
        )

        self.scheduler.start()
        self.started = True
        logger.info("[GitHub Star Monitor] Scheduler started")

    async def shutdown(self):
        if self.started:
            self.scheduler.shutdown(wait=False)
            self.started = False
            logger.info("[GitHub Star Monitor] Scheduler stopped")
