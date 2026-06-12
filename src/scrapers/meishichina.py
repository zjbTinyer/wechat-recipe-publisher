"""
美食天下 (meishichina.com) 爬虫
作为豆果美食的备选源
注意: recipe 页面在 home.meishichina.com 子域名
"""
import logging
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Recipe
from ..utils.retry import retry

logger = logging.getLogger("recipe_publisher")

# 美食天下域名
WWW_BASE = "https://www.meishichina.com"
HOME_BASE = "https://home.meishichina.com"

# 食谱列表页
LIST_URLS = [
    f"{HOME_BASE}/recipe.html",
    f"{HOME_BASE}/recipe-menu.html",
    f"{HOME_BASE}/show-top-type-recipe.html",
]


class MeishichinaScraper(BaseScraper):
    """美食天下爬虫"""

    SOURCE_NAME = "美食天下"
    BASE_URL = HOME_BASE

    def get_recipe_list(self, category: str = "家常菜") -> List[str]:
        """从列表页获取食谱链接"""
        urls = []

        for list_url in LIST_URLS:
            logger.info(f"[{self.SOURCE_NAME}] 请求列表页: {list_url}")
            try:
                resp = self._fetch_page(list_url)
            except Exception as e:
                logger.warning(f"[{self.SOURCE_NAME}] 列表页请求失败: {e}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # 查找 recipe-{id}.html 格式的链接
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if "recipe-" in href and href.endswith(".html"):
                    # 过滤掉分类/列表页，只保留单个食谱
                    if any(x in href for x in ["recipe-type", "recipe-menu",
                                                 "recipe-list", "show-top"]):
                        continue
                    full_url = urljoin(HOME_BASE, href)
                    if full_url not in urls:
                        urls.append(full_url)

            if urls:
                logger.info(f"[{self.SOURCE_NAME}] 找到 {len(urls)} 个食谱链接")
                break

        return urls

    def parse_recipe_detail(self, url: str) -> Optional[Recipe]:
        """解析食谱详情页"""
        logger.info(f"[{self.SOURCE_NAME}] 解析详情: {url}")
        resp = self._fetch_page(url)
        soup = BeautifulSoup(resp.text, "lxml")

        # 标题
        title_el = soup.select_one("h1#recipe_title, h1.recipe_De_title, h1")
        if not title_el:
            logger.warning(f"[{self.SOURCE_NAME}] 未找到标题元素")
            return None
        title = title_el.get_text(strip=True)

        # 封面图（美食天下使用 data-src 延迟加载）
        cover_url = ""
        for sel in ["div.recipe_cover img#recipe_img",
                     "div.recipe_cover img",
                     ".recipe_cover img"]:
            cover_el = soup.select_one(sel)
            if cover_el:
                cover_url = cover_el.get("data-src", "") or cover_el.get("src", "")
                if cover_url:
                    break

        # 食材
        ingredients = []
        for li in soup.select("div.materials ul.ylist li, div.materials li"):
            name_el = li.select_one("span.left, h4, b, .scname")
            weight_el = li.select_one("span.right, i, .scnum")
            if name_el:
                name = name_el.get_text(strip=True)
                weight = weight_el.get_text(strip=True) if weight_el else "适量"
                if name:
                    ingredients.append((name, weight))

        # 步骤
        steps = []
        step_images = []
        for li in soup.select("div.step_container ol li, div.recipe_step ol li"):
            text_el = li.select_one("div.text, p, span")
            img_el = li.select_one("img")
            if text_el:
                steps.append(text_el.get_text(strip=True))
            if img_el:
                img_src = img_el.get("data-src", "") or img_el.get("src", "")
                if img_src and "blank" not in img_src:
                    step_images.append(img_src)

        if not steps:
            logger.warning(f"[{self.SOURCE_NAME}] 未找到步骤")
            return None

        return Recipe(
            title=title,
            cover_image_url=cover_url,
            ingredients=ingredients,
            steps=steps,
            step_images=step_images,
        )

    @retry(max_attempts=3, base_delay=2.0, exceptions=(Exception,))
    def _fetch_page(self, url: str):
        """请求页面，带重试"""
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        return resp
