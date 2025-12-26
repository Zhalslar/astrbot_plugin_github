import aiohttp

from astrbot.api import logger


class GitHubRequest:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None):
        self.headers = {
            "User-Agent": "AstrBot-GitHub-Star-Monitor/1.0.0",
            "Accept": "application/vnd.github.v3+json",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

        self.session: aiohttp.ClientSession | None = None

    async def start(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def _get(self, url: str, **kwargs):
        if not self.session:
            raise RuntimeError("GitHubRequest not initialized")

        async with self.session.get(url, headers=self.headers, **kwargs) as resp:
            return resp.status, await resp.json()

    async def get_user_repos(self, username: str) -> list[str]:
        """获取用户所有公开仓库"""
        repos: list[str] = []
        page = 1

        while True:
            status, data = await self._get(
                url=f"{self.BASE_URL}/users/{username}/repos",
                params={"per_page": 100, "page": page},
            )

            if status != 200:
                logger.warning(f"GitHubAPI: 获取用户仓库失败 {status}")
                break

            if not data:
                break

            for repo in data:
                if full := repo.get("full_name"):
                    repos.append(full)

            page += 1

        return repos

    async def get_repo_info(self, repo: str) -> dict | None:
        status, data = await self._get(url=f"{self.BASE_URL}/repos/{repo}")

        if status != 200:
            logger.warning(f"GitHubAPI: 获取仓库信息失败 {status}")
            return None

        return data

    async def get_stargazers(self, repo: str, page: int, per_page: int) -> list[dict]:
        status, data = await self._get(
            url=f"{self.BASE_URL}/repos/{repo}/stargazers",
            params={"page": page, "per_page": per_page},
        )

        if status != 200:
            logger.warning(f"GitHubAPI: 获取 stargazers 失败 {status}")
            return []

        return data
