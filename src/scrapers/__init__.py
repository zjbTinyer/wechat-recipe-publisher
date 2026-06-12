"""
爬虫模块
按优先级注册爬虫，支持自动回退
"""
import random
import logging
from typing import Dict, Type

from .base import BaseScraper, Recipe
from .xiachufang import XiachufangScraper
from .meishichina import MeishichinaScraper
from .douguo import DouguoScraper

logger = logging.getLogger("recipe_publisher")

# 爬虫注册表
SCRAPERS: Dict[str, Type[BaseScraper]] = {
    "xiachufang": XiachufangScraper,
    "meishichina": MeishichinaScraper,
    "douguo": DouguoScraper,
}


def fetch_recipe(primary: str = "douguo",
                 category: str = "家常菜") -> Recipe:
    """按优先级抓取食谱，失败自动回退到下一个源

    Args:
        primary: 首选爬虫名称
        category: 食谱分类

    Returns:
        Recipe 对象

    Raises:
        RuntimeError: 所有爬虫都失败时抛出
    """
    # 构建尝试顺序：首选 → 其他 → 随机打乱的剩余
    source_names = [primary] + [s for s in SCRAPERS if s != primary]

    for name in source_names:
        scraper_cls = SCRAPERS.get(name)
        if not scraper_cls:
            logger.warning(f"未知爬虫源: {name}，跳过")
            continue

        try:
            logger.info(f"尝试从 [{name}] 抓取食谱...")
            scraper = scraper_cls()
            recipe = scraper.get_random_recipe(category)

            # 校验数据完整性
            if not recipe or not recipe.title or not recipe.steps:
                logger.warning(f"[{name}] 返回的食谱数据不完整，回退到下一个源")
                continue

            logger.info(f"[{name}] 抓取成功: {recipe.title}")
            return recipe

        except Exception as e:
            logger.error(f"[{name}] 抓取失败: {e}", exc_info=True)
            continue

    raise RuntimeError(
        f"所有爬虫源都失败了，尝试过: {source_names}"
    )
