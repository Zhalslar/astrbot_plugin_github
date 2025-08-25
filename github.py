from pathlib import Path
import aiohttp
from typing import Optional
from astrbot import logger
from .data import JsonStorage


class GitHubAPI:
    base_url = "https://api.github.com"
    headers = {
        "User-Agent": "AstrBot-GitHub-Star-Monitor/1.0.0",
        "Accept": "application/vnd.github.v3+json",
    }

    def __init__(self, token: str | None, repositories: list[str], data_file: Path):
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.storage = JsonStorage(data_file)
        self.last_star_counts: dict[str, int] = self.storage.load()
        self.session = aiohttp.ClientSession()
        self.repositories = repositories
        self.is_monitoring = False  # 添加监控状态标志

    async def initialize(self):
        self.repo_infos = await self.parse_github_urls()
        for repo in self.repo_infos:
            self.last_star_counts.setdefault(repo, 0)
        self.storage.save(self.last_star_counts)

    async def parse_github_urls(self) -> list[str]:
        """
        接收多个 GitHub 链接，返回所有解析出的 owner/repo 列表。

        支持仓库链接和用户主页链接：
        - 仓库链接返回一个 owner/repo
        - 用户主页链接返回该用户所有公开仓库
        """
        results: list[str] = []

        for url in self.repositories:
            try:
                for prefix in (
                    "https://github.com/",
                    "http://github.com/",
                    "github.com/",
                ):
                    if url.startswith(prefix):
                        url = url[len(prefix) :]
                        break

                path = url.rstrip("/").removesuffix(".git")
                if "/" in path:
                    results.append(path)
                else:
                    repos = await self.get_repos_by_user(path)
                    results.extend(repos)
            except Exception as e:
                logger.error(f"GitHubAPI: 解析 URL 失败：{url}，错误：{e}")

        return results

    async def get_repos_by_user(self, username: str) -> list[str]:
        """
        获取指定 GitHub 用户的所有公开仓库（格式为 owner/repo）
        """
        url = f"{self.base_url}/users/{username}/repos?per_page=100"
        repos = []

        try:
            page = 1
            while True:
                paged_url = f"{url}&page={page}"
                async with self.session.get(paged_url, headers=self.headers) as resp:
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
            logger.info(f"GitHubAPI: 已获取仓库: \n{repos}")
            return repos
        except Exception as e:
            logger.error(f"GitHubAPI: 获取仓库失败: {e}")
            return []

    async def get_repo_stars(self, repo_info: str) -> Optional[int]:
        """
        获取并更新仓库的 star 总数
        """
        url = f"{self.base_url}/repos/{repo_info}"
        async with self.session.get(url, headers=self.headers) as resp:
            if resp.status == 200:
                detail = await resp.json()
                star_count = detail.get("stargazers_count")
                if star_count is not None:
                    if self.last_star_counts[repo_info] != star_count:
                        self.last_star_counts[repo_info] = star_count
                        logger.info(f"{repo_info}⭐数量更新: {star_count}")
                        self.storage.save(self.last_star_counts)
                    return star_count
            else:
                logger.warning(
                    f"[GitHub Star Monitor] 获取仓库信息失败，状态码: {resp.status}"
                )

    async def get_star_change_users(
        self, repo_info: str, total_stars: int, change_count: int, per_page: int= 25
    ) -> str | None:
        """
        获取最近一次 star 变动的用户名
        change_count > 0 : 取最新的 star 用户
        change_count <=0 : 直接返回 '某人'
        """
        if change_count <= 0:
            return "某人"

        try:
            last_page = max(1, (total_stars + per_page - 1) // per_page)

            url = f"{self.base_url}/repos/{repo_info}/stargazers"
            async with self.session.get(
                url,
                headers=self.headers,
                params={"per_page": per_page, "page": last_page},
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        f"GitHubAPI: 获取 stargazers 失败，状态码: {resp.status}"
                    )
                    return None

                stargazers = await resp.json()
                recent = stargazers[-abs(change_count) :] if stargazers else []

            # 2. 提取用户名
            names = [s.get("login") for s in recent]
            return ", ".join(names)

        except Exception as e:
            logger.error(f"GitHubAPI: 获取变动用户名失败: {e}")
            return None

    async def check_repositories(self) -> list[str] | None:
        """检查所有仓库的星标变化"""
        if self.is_monitoring:
            logger.debug("GitHub Star Monitor: 上一次检查还在进行中，跳过本次检查")
            return
        self.is_monitoring = True
        msgs = []
        for repo_info in self.repo_infos:
            try:
                last_stars = self.last_star_counts.get(repo_info)
                current_stars = await self.get_repo_stars(repo_info)

                if current_stars and last_stars and current_stars != last_stars:
                    # 星标数量发生变化
                    change_count = current_stars - last_stars
                    # 获取导致此次变动的具体用户
                    change_users = await self.get_star_change_users(
                        repo_info=repo_info,
                        total_stars=current_stars,
                        change_count=change_count,
                    )

                    msgs.append(
                        f"{repo_info.split('/')[1]}：{change_users}{'点了⭐' if change_count > 0 else '取消了⭐'}，当前{current_stars}⭐"
                    )
                    logger.info(
                        f"[GitHub Star Monitor] 检测到 {repo_info} ⭐变动: {last_stars} -> {current_stars}"
                    )

            except Exception as e:
                logger.error(f"GitHub Star Monitor: 检查仓库 {repo_info} 时出错: {e}")
                pass

        self.is_monitoring = False
        return msgs

    async def close(self):
        if self.session:
            await self.session.close()
