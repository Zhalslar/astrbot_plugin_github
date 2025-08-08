from datetime import datetime
import aiohttp
from typing import Optional
from astrbot import logger


class GitHubAPI:
    def __init__(self, token: str | None):
        self.headers = {
            "User-Agent": "AstrBot-GitHub-Star-Monitor/1.0.0",
            "Accept": "application/vnd.github.v3+json",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self._star_cache: dict[str, set[str]] = {}

    async def initialize_star_cache(self, repo_info: str) -> None:
        """
        初始化指定仓库的 star 缓存，避免第一次比较时误判
        """
        if repo_info not in self._star_cache:
            star_list = await self._get_recent_stargazers(repo_info)
            if star_list is not None:
                self._star_cache[repo_info] = set(star_list)
            else:
                self._star_cache[repo_info] = set()
            logger.info(f"GitHubAPI: 初始化 {repo_info} 的star缓存，数量：{len(self._star_cache[repo_info])}")

    async def parse_github_urls(self, urls: list[str]) -> list[str]:
        """
        接收多个 GitHub 链接，返回所有解析出的 owner/repo 列表。

        支持仓库链接和用户主页链接：
        - 仓库链接返回一个 owner/repo
        - 用户主页链接返回该用户所有公开仓库
        """
        results: list[str] = []

        for url in urls:
            try:
                for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
                    if url.startswith(prefix):
                        url = url[len(prefix):]
                        break

                path = url.rstrip("/").removesuffix(".git")
                parts = path.split("/")

                if len(parts) == 1:
                    # 用户主页，如 github.com/username
                    username = parts[0]
                    repos = await self.get_repos_by_user(username)
                    results.extend(repos)
                elif len(parts) >= 2:
                    # 仓库地址，如 github.com/username/reponame
                    owner, repo = parts[:2]
                    results.append(f"{owner}/{repo}")
            except Exception as e:
                logger.error(f"GitHubAPI: 解析 URL 失败：{url}，错误：{e}")

        return results



    async def get_repo_detail(self, repo_info: str) -> Optional[dict]:
        """
        获取仓库详情信息（如描述、star数等）
        """
        url = f"https://api.github.com/repos/{repo_info}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning(
                        f"GitHub Star Monitor: 获取仓库信息失败，状态码: {resp.status}"
                    )
                    return None

    async def get_repo_stars(self, repo_info: str) -> Optional[int]:
        """
        获取仓库的 star 总数
        """
        detail = await self.get_repo_detail(repo_info)
        return detail.get("stargazers_count") if detail else None

    async def get_star_change_events(
        self, repo_info: str, change_count: int
    ) -> list[dict]:
        """根据变动数量返回最新的 star/unstar 用户事件"""
        if change_count > 0:
            return await self._get_latest_stars(repo_info, change_count)
        else:
            return await self._get_unstar_events(repo_info)

    async def _get_latest_stars(self, repo_info: str, change_count: int) -> list[dict]:
        try:
            repo_detail = await self.get_repo_detail(repo_info)
            if not repo_detail:
                return []

            total_stars = repo_detail.get("stargazers_count", 0)
            per_page = 100
            last_page = max(1, (total_stars + per_page - 1) // per_page)

            url = f"https://api.github.com/repos/{repo_info}/stargazers"
            headers = self.headers.copy()
            headers["Accept"] = "application/vnd.github.v3.star+json"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    params={"per_page": per_page, "page": last_page},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        stargazers = await resp.json()
                        recent = stargazers[-abs(change_count):] if stargazers else []

                        result = [
                            {
                                "type": "WatchEvent",
                                "actor": s.get("user", {}),
                                "created_at": s.get("starred_at", datetime.now().isoformat() + "Z"),
                            }
                            for s in recent
                        ]
                        result.sort(key=lambda x: x["created_at"], reverse=True)
                        logger.info(f"GitHubAPI: 获取到 {len(result)} 个最新 star 用户")
                        return result
                    else:
                        logger.warning(f"GitHubAPI: 获取 stargazers 失败，状态码: {resp.status}")
                        return []
        except Exception as e:
            logger.error(f"GitHubAPI: 获取 star 用户失败: {e}")
            return []

    async def _get_unstar_events(self, repo_info: str) -> list[dict]:
        """通过 events API 获取最近 WatchEvent（GitHub 不支持明确 unstar）"""
        try:
            url = f"https://api.github.com/repos/{repo_info}/events"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        events = await resp.json()
                        watch_events = [e for e in events if e.get("type") == "WatchEvent"]
                        logger.info(f"GitHubAPI: 获取 {len(watch_events)} 个 WatchEvent")
                        return watch_events[:1]
                    else:
                        logger.warning(f"GitHubAPI: 获取 events 失败，状态码: {resp.status}")
                        return []
        except Exception as e:
            logger.error(f"GitHubAPI: 获取 unstar 事件失败: {e}")
            return []

    async def get_star_change_users(self, repo_info: str, change_count: int) -> str | None:
        """
        获取最近一次 star/unstar 的用户名（结合事件和内存缓存差异）
        """
        event_names = []
        try:
            if change_count > 0:
                events = await self.get_star_change_events(repo_info, change_count=1)
                if events:
                    for event in events:
                        if event.get("type") != "WatchEvent":
                            continue
                        actor = event.get("actor")
                        if isinstance(actor, dict):
                            name = actor.get("login") or actor.get("name")
                            if name:
                                event_names.append(name)
                                return ", ".join(event_names)
            if change_count < 0:
                current = await self._get_recent_stargazers(repo_info)
                if current is None:
                    return None

                current_set = set(current)
                previous_set = self._star_cache.get(repo_info, set())

                removed = previous_set - current_set
                # 更新缓存
                return ", ".join(removed) if removed else None
            else:
                return None

        except Exception as e:
            logger.error(f"GitHubAPI: 获取变动用户名失败: {e}")
            return None

    async def _get_recent_stargazers(self, repo_info: str) -> list[str] | None:
        """
        获取最近 100 个 star 的用户登录名列表
        """
        url = f"https://api.github.com/repos/{repo_info}/stargazers?per_page=100"
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.v3.star+json"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"GitHubAPI: 获取 stargazers 失败（{resp.status}）: {await resp.text()}"
                        )
                        return None
                    data = await resp.json()

            usernames = []
            for item in data:
                if isinstance(item, dict) and "user" in item:
                    user = item["user"]
                    name = user.get("login")
                else:
                    name = item.get("login")
                if name:
                    usernames.append(name)

            return usernames
        except Exception as e:
            logger.error(f"GitHubAPI: 获取 stargazers 异常: {e}")
            return None

    async def get_repos_by_user(self, username: str) -> list[str]:
        """
        获取指定 GitHub 用户的所有公开仓库（格式为 owner/repo）
        """
        url = f"https://api.github.com/users/{username}/repos?per_page=100"
        repos = []

        try:
            async with aiohttp.ClientSession() as session:
                page = 1
                while True:
                    paged_url = f"{url}&page={page}"
                    async with session.get(paged_url, headers=self.headers) as resp:
                        if resp.status != 200:
                            logger.warning(
                                f"GitHubAPI: 获取用户仓库失败（{resp.status}）: {await resp.text()}"
                            )
                            break

                        data = await resp.json()
                        if not data:
                            break 

                        for repo in data:
                            full_name = repo.get("full_name")
                            if full_name:
                                repos.append(full_name)

                        page += 1

            return repos
        except Exception as e:
            logger.error(f"GitHubAPI: 获取用户公开仓库失败: {e}")
            return []
