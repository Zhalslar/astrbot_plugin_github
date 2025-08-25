import asyncio
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.star.star_tools import StarTools
from .github import GitHubAPI


@register(
    "astrbot_plugin_github",
    "Jason.Joestar",
    "专门对接github的插件",
    "1.0.0",
    "https://github.com/advent259141/astrbot_plugin_github",
)
class GitHubStarMonitor(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.conf = config
        self.data_file = (
            StarTools.get_data_dir("astrbot_plugin_github") / "github_stars.json"
        )

    async def initialize(self):
        self.github = GitHubAPI(
            token=self.conf["github_token"],
            repositories=self.conf["repositories"],
            data_file=self.data_file,
        )
        await self.github.initialize()
        self.monitoring_task = asyncio.create_task(self.start_monitoring())

    async def start_monitoring(self):
        """启动监控任务"""
        if not self.conf["target_sessions"]:
            logger.warning("[GitHub Star Monitor] 未配置通知会话，监控任务取消")
            return
        if not self.github.repo_infos:
            logger.info("[GitHub Star Monitor] 未配置监控仓库，监控任务取消")
            return
        try:
            logger.info("[GitHub Star Monitor] 开始监控任务")
            while True:
                try:
                    await self.check_repositories()
                    await asyncio.sleep(self.conf["check_interval"])
                except Exception as e:
                    logger.error(f"[GitHub Star Monitor] 监控任务出错: {e}")
                    await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"[GitHub Star Monitor] 启动监控任务失败: {e}")

    async def check_repositories(self):
        """检查所有仓库的星标变化"""
        if message := await self.github.check_repositories():
            for session_id in self.conf["target_sessions"]:
                try:
                    await self.context.send_message(
                        session=session_id,
                        message_chain=MessageChain([Comp.Plain("\n".join(message))]),
                    )
                except Exception as e:
                    logger.error(
                        f"GitHub Star Monitor: 向会话 {session_id} 发送通知失败: {e}"
                    )

    @filter.command("star")
    async def star_force_check(self, event: AstrMessageEvent):
        """检查所有仓库"""
        yield event.plain_result("开始检查所有仓库...")
        try:
            await self.check_repositories()
            yield event.plain_result("检查完成")
        except Exception as e:
            yield event.plain_result(f"检查失败: {e}")

    @filter.command("starls")
    async def star_status(self, event: AstrMessageEvent):
        """查看当前监控的仓库星标状态（按星标数倒序）"""
        infos = self.github.last_star_counts.copy()
        print(infos)
        sorted_items = sorted(infos.items(), key=lambda x: x[1], reverse=True)
        msg = "\n\n".join(f"{name}: {stars}⭐" for name, stars in sorted_items)
        image = await self.text_to_image(msg)
        yield event.image_result(image)

    async def terminate(self):
        """插件卸载时调用"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
        await self.github.close()
        logger.info("GitHub Star Monitor: 插件已停止")
