"""
配置管理模块
从环境变量加载所有配置项，支持本地 .env 文件和 GitHub Actions Secrets
"""
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """应用配置"""
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    log_level: str = "INFO"
    recipes_dir: str = "./recipes"
    primary_scraper: str = "douguo"
    recipe_category: str = "家常菜"
    # 公众号文章作者名（最多 16 字符）
    author_name: str = "每日家常菜"

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置"""
        # 尝试加载 .env 文件（本地开发用）
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        wechat_app_id = os.environ.get("WECHAT_APP_ID", "")
        wechat_app_secret = os.environ.get("WECHAT_APP_SECRET", "")

        if not wechat_app_id or not wechat_app_secret:
            raise ValueError(
                "缺少必要的环境变量: WECHAT_APP_ID 和 WECHAT_APP_SECRET 必须设置"
            )

        return cls(
            wechat_app_id=wechat_app_id,
            wechat_app_secret=wechat_app_secret,
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            recipes_dir=os.environ.get("RECIPES_DIR", "./recipes"),
            primary_scraper=os.environ.get("PRIMARY_SCRAPER", "douguo"),
            recipe_category=os.environ.get("RECIPE_CATEGORY", "家常菜"),
            author_name=os.environ.get("AUTHOR_NAME", "每日家常菜"),
        )
