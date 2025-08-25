import json
from pathlib import Path
from astrbot.api import logger


class JsonStorage:
    """把 dict 持久化到本地 json"""

    def __init__(self, data_file: Path):
        self.file = data_file
        self.file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if self.file.exists():
            try:
                with open(self.file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save(self, data: dict) -> None:
        try:
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"GitHubAPI: 保存 json 失败: {e}")
