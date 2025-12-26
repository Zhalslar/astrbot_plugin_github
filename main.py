
import asyncio

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.star.star_tools import StarTools

from .core.data import JsonStorage
from .core.request import GitHubRequest
from .core.scheduler import GitHubScheduler
from .core.service import GitHubService
from .core.utils import parse_bool


class GitHubPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.conf = config
        self.data_dir = StarTools.get_data_dir("astrbot_plugin_github")
        self.data_file = self.data_dir / "github_stars.json"

    async def initialize(self):
        self.storage = JsonStorage(self.data_file)
        self.request = GitHubRequest(self.conf["token"])
        await self.request.start()
        self.service = GitHubService(self.context, self.conf, self.storage, self.request)
        await asyncio.create_task(self.service.parse_repositories())

        if not self.conf["target_sessions"]:
            logger.debug("[GitHub Star Monitor] 未配置通知会话，监控任务取消")
            return
        if not self.conf["repositories"]:
            logger.info("[GitHub Star Monitor] 未配置监控仓库，监控任务取消")
            return

        self.scheduler = GitHubScheduler(self.conf, self.service)
        self.scheduler.start()

    async def terminate(self):
        if self.scheduler:
            await self.scheduler.shutdown()
        if self.request:
            await self.request.close()

        logger.info("GitHub Star Monitor: 插件已停止")

    @filter.command("github")
    async def star_check(
        self, event: AstrMessageEvent, mode_str: str | bool | None = None
    ):
        """检查所有仓库"""
        mode = parse_bool(mode_str)
        umo = event.unified_msg_origin
        if mode is True:
            self.conf["target_sessions"].append(umo)
            self.conf.save_config()
            yield event.plain_result("已在当前会话开启github通知")
        else:
            self.conf["target_sessions"].remove(umo)
            self.conf.save_config()
            yield event.plain_result("已在当前会话关闭github通知")

    @filter.command("star")
    async def star_force_check(self, event: AstrMessageEvent):
        """检查所有仓库"""
        yield event.plain_result("开始检查所有仓库...")
        await self.service.check_repositories()

    @filter.command("starls")
    async def star_status(self, event: AstrMessageEvent):
        """查看当前监控的仓库星标状态（按星标数倒序）"""
        infos = self.service.last_star_counts.copy()
        sorted_items = sorted(infos.items(), key=lambda x: x[1], reverse=True)
        msg = "\n\n".join(f"{name}: {stars}⭐" for name, stars in sorted_items)
        image = await self.text_to_image(msg)
        yield event.image_result(image)


