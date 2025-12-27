import asyncio

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.star.context import Context

from .data import JsonStorage
from .request import GitHubRequest


class GitHubService:
    def __init__(
        self, context: Context, config: AstrBotConfig, storage: JsonStorage, request: GitHubRequest
    ):
        self.context = context
        self.conf = config
        self.storage = storage
        self.request = request

        self.last_star_counts: dict[str, int] = self.storage.load()
        self.is_monitoring = False
        asyncio.create_task(self.parse_repositories())

    async def parse_repositories(self) -> list[str]:
        """
        解析用户配置的仓库：
        - 已是 owner/repo 的直接保留
        - 用户主页解析为其所有公开仓库
        - 解析完成后覆盖原始配置
        """
        parsed: list[str] = []

        for raw in self.conf["repositories"]:
            try:
                url = raw.strip()

                # 去除 GitHub 前缀
                for prefix in (
                    "https://github.com/",
                    "http://github.com/",
                    "github.com/",
                ):
                    if url.startswith(prefix):
                        url = url[len(prefix) :]
                        break

                path = url.rstrip("/").removesuffix(".git")

                # 已是标准仓库格式：owner/repo
                if "/" in path:
                    parsed.append(path)
                    continue

                # 否则视为用户主页
                repos = await self.request.get_user_repos(path)
                parsed.extend(repos)

            except Exception as e:
                logger.error(f"GitHubService: 解析失败 {raw} -> {e}")

        # 覆盖原始配置，保证后续逻辑只处理规范数据
        self.conf["repositories"] = parsed
        self.conf.save_config()

        return parsed

    async def get_star_change_users(
        self, repo: str, total: int, diff: int, per_page: int = 25
    ) -> str | None:
        if diff <= 0:
            return "有人"

        last_page = max(1, (total + per_page - 1) // per_page)

        users = await self.request.get_stargazers(
            repo, page=last_page, per_page=per_page
        )

        recent = users[-abs(diff) :]
        names = [u["login"] for u in recent if isinstance(u.get("login"), str)]
        return ", ".join(names)

    async def _check_repositories(self) -> list[str] | None:
        if self.is_monitoring:
            logger.debug("GitHub Star Monitor: 上一次任务仍在执行")
            return None

        self.is_monitoring = True
        messages: list[str] = []

        try:
            for repo in self.conf["repositories"]:
                info = await self.request.get_repo_info(repo)
                if not info:
                    continue

                current = info.get("stargazers_count")
                if current is None:
                    continue

                # —— 首次写入：只记录，不推送 ——
                if repo not in self.last_star_counts:
                    self.last_star_counts[repo] = current
                    self.storage.save(self.last_star_counts)
                    logger.debug(f"[GitHub Star Monitor] 初始化 {repo} = {current}")
                    continue

                last = self.last_star_counts[repo]

                if current == last:
                    continue

                diff = current - last
                users = await self.get_star_change_users(repo, current, diff)

                self.last_star_counts[repo] = current
                self.storage.save(self.last_star_counts)

                messages.append(
                    f"{repo.split('/')[-1]}："
                    f"{users}{'点了⭐' if diff > 0 else '取消了⭐'}，当前{current}⭐"
                )

                logger.info(f"[GitHub Star Monitor] {repo}: {last} → {current}")

        finally:
            self.is_monitoring = False

        return messages

    async def check_repositories(self):
        """检查所有仓库的星标变化"""
        if message := await self._check_repositories():
            for session_id in self.conf["target_sessions"]:
                try:
                    await self.context.send_message(
                        session=session_id,
                        message_chain=MessageChain([Plain("\n".join(message))]),
                    )
                except Exception as e:
                    logger.error(
                        f"GitHub Star Monitor: 向会话 {session_id} 发送通知失败: {e}"
                    )
