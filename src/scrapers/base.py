"""
爬虫基类模块
定义 Recipe 数据模型和 BaseScraper 抽象接口
"""
import random
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

logger = logging.getLogger("recipe_publisher")


@dataclass
class Recipe:
    """食谱数据模型"""
    title: str                                    # 菜名
    cover_image_url: str = ""                     # 封面图 URL
    ingredients: List[Tuple[str, str]] = field(default_factory=list)  # [(名称, 用量), ...]
    steps: List[str] = field(default_factory=list)                     # 步骤描述
    step_images: List[str] = field(default_factory=list)               # 步骤图片 URL
    source_url: str = ""                           # 原始食谱链接
    source_name: str = ""                          # 来源网站名称

    @property
    def summary(self) -> str:
        """自动生成摘要（取前两个步骤拼接）"""
        if not self.steps:
            return f"今天为大家带来一道美味的{self.title}，简单易学，快来试试吧！"
        text = "".join(self.steps[:2])
        if len(text) > 100:
            text = text[:97] + "..."
        return f"{self.title} — {text}"


class BaseScraper(ABC):
    """爬虫抽象基类"""

    # 子类需覆盖
    SOURCE_NAME: str = "unknown"
    BASE_URL: str = ""

    def __init__(self):
        self.session = self._create_session()

    def _create_session(self):
        """创建带基础 headers 的 requests Session"""
        import requests
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        })
        return session

    @abstractmethod
    def get_recipe_list(self, category: str) -> List[str]:
        """获取食谱列表页中的详情 URL 列表

        Args:
            category: 食谱分类（如"家常菜"）

        Returns:
            详情页 URL 列表
        """
        ...

    @abstractmethod
    def parse_recipe_detail(self, url: str) -> Optional[Recipe]:
        """解析食谱详情页，提取完整 Recipe 信息

        Args:
            url: 食谱详情页 URL

        Returns:
            Recipe 对象，解析失败返回 None
        """
        ...

    def get_random_recipe(self, category: str = "家常菜") -> Optional[Recipe]:
        """从列表中随机选取一个食谱并解析详情

        Args:
            category: 食谱分类

        Returns:
            Recipe 对象
        """
        urls = self.get_recipe_list(category)
        if not urls:
            logger.warning(f"[{self.SOURCE_NAME}] 未获取到食谱列表")
            return None

        logger.info(f"[{self.SOURCE_NAME}] 获取到 {len(urls)} 个食谱链接")

        # 随机打乱，逐个尝试解析直到成功
        shuffled = list(urls)
        random.shuffle(shuffled)

        # 最多尝试 10 个
        for url in shuffled[:10]:
            try:
                recipe = self.parse_recipe_detail(url)
                if recipe and recipe.title and recipe.steps:
                    recipe.source_url = url
                    recipe.source_name = self.SOURCE_NAME
                    return recipe
            except Exception as e:
                logger.warning(f"[{self.SOURCE_NAME}] 解析详情失败 {url}: {e}")
                continue

        return None
