import asyncio
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp
from astrbot.core.message.message_event_result import MessageChain
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
        self.check_interval: int = config.get("check_interval", 60)
        self.repositories: list = config.get("repositories", [])
        self.target_sessions: list = config.get("target_sessions", [])
        self.github_token: str = config.get("github_token", "")
        self.last_star_counts: dict[str, int] = {}
        self.is_monitoring = False  # 添加监控状态标志
        self.monitoring_task = None

    async def initialize(self):
        self.github = GitHubAPI(token=self.github_token)
        self.repo_infos = await self.github.parse_github_urls(self.repositories)
        self.monitoring_task = asyncio.create_task(self.start_monitoring())

    async def start_monitoring(self):
        """启动监控任务"""
        try:
            logger.info("GitHub Star Monitor: 开始监控任务")

            await self.init_star_counts()

            while True:
                try:
                    await self.check_repositories()
                    await asyncio.sleep(self.check_interval)
                except Exception as e:
                    logger.error(f"GitHub Star Monitor: 监控任务出错: {e}")
                    await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"GitHub Star Monitor: 启动监控任务失败: {e}")


    async def init_star_counts(self):
        """初始化星标数据"""
        for repo_info in self.repo_infos:
            if repo_info not in self.last_star_counts:
                try:
                    current_stars = await self.github.get_repo_stars(repo_info)
                    if current_stars is not None:
                        self.last_star_counts[repo_info] = current_stars
                        logger.info(
                            f"GitHub Star Monitor: 初始化 {repo_info} 星标数: {current_stars}"
                        )
                except Exception as e:
                    logger.error(
                        f"GitHub Star Monitor: 初始化 {repo_info} 星标数失败: {e}"
                    )

    async def check_repositories(self):
        """检查所有仓库的星标变化"""
        if self.is_monitoring:
            logger.debug("GitHub Star Monitor: 上一次检查还在进行中，跳过本次检查")
            return

        self.is_monitoring = True

        try:
            if not self.repositories:
                logger.debug("GitHub Star Monitor: 没有配置要监控的仓库")
                return

            if not self.target_sessions:
                logger.debug("GitHub Star Monitor: 没有配置目标会话")
                return

            for repo_info in self.repo_infos:
                try:
                    current_stars = await self.github.get_repo_stars(repo_info)

                    if current_stars is None:
                        continue
                    last_stars = self.last_star_counts.get(repo_info)
                    if last_stars is not None and current_stars != last_stars:
                        # 星标数量发生变化
                        change_count = current_stars - last_stars

                        # 立即更新记录，防止重复通知
                        self.last_star_counts[repo_info] = current_stars

                        # 获取导致此次变动的具体用户
                        change_users = await self.github.get_star_change_users(repo_info, change_count)

                        message = f"仓库{repo_info}：{change_users}{'点了⭐' if change_count > 0 else '取消了⭐'}，当前{current_stars}⭐"

                        for session_id in self.target_sessions:
                            try:
                                await self.context.send_message(
                                    session=session_id,
                                    message_chain=MessageChain([Comp.Plain(message)]),
                                )
                                logger.info(f"GitHub Star Monitor: 已向会话 {session_id} 发送通知")
                            except Exception as e:
                                logger.error(
                                    f"GitHub Star Monitor: 向会话 {session_id} 发送通知失败: {e}"
                                )

                        logger.info(
                            f"GitHub Star Monitor: 检测到 {repo_info} 星标变动: {last_stars} -> {current_stars}"
                        )
                    else:
                        # 更新记录的星标数
                        self.last_star_counts[repo_info] = current_stars

                except Exception as e:
                    logger.error(
                        f"GitHub Star Monitor: 检查仓库 {repo_info} 时出错: {e}"
                    )
        finally:
            self.is_monitoring = False


    @filter.command("star列表")
    async def star_status(self, event: AstrMessageEvent):
        """查看当前监控的仓库星标状态"""
        if not self.repositories:
            yield event.plain_result("当前没有配置要监控的仓库")
            return
        status_text = ""
        for repo_info in self.repo_infos:
            try:
                current_stars = await self.github.get_repo_stars(repo_info)
                if current_stars:
                    status_text += f"{repo_info}: {current_stars}⭐\n"
                else:
                    status_text += f"{repo_info}: 获取失败\n"
            except Exception as e:
                status_text += f"{repo_info}: 检查出错{e}\n"

        yield event.plain_result(status_text.strip())


    @filter.command("star检查")
    async def star_force_check(self, event: AstrMessageEvent):
        """强制检查所有仓库"""
        yield event.plain_result("开始检查所有仓库...")

        try:
            await self.check_repositories()
            yield event.plain_result("检查完成")
        except Exception as e:
            yield event.plain_result(f"检查失败: {e}")

    async def terminate(self):
        """插件卸载时调用"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
        logger.info("GitHub Star Monitor: 插件已停止")
