"""
下厨房 (xiachufang.com) 爬虫
抓取家常菜分类的食谱列表和详情
"""
import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Recipe
from ..utils.retry import retry

logger = logging.getLogger("recipe_publisher")

# 下厨房家常菜分类 ID
CATEGORY_IDS = {
    "家常菜": "40076",
    "快手菜": "40073",
    "下饭菜": "40078",
    "素菜": "40075",
}


class XiachufangScraper(BaseScraper):
    """下厨房爬虫"""

    SOURCE_NAME = "下厨房"
    BASE_URL = "https://www.xiachufang.com"

    def get_recipe_list(self, category: str = "家常菜") -> List[str]:
        """从分类列表页获取食谱链接"""
        category_id = CATEGORY_IDS.get(category, "40076")
        list_url = f"{self.BASE_URL}/category/{category_id}/"

        logger.info(f"[{self.SOURCE_NAME}] 请求列表页: {list_url}")
        resp = self._fetch_page(list_url)
        soup = BeautifulSoup(resp.text, "lxml")

        urls = []
        # 列表项中的食谱链接
        for item in soup.select("div.info.pure-u p.name a"):
            href = item.get("href", "")
            if href and "/recipe/" in href:
                full_url = urljoin(self.BASE_URL, href)
                urls.append(full_url)

        return urls

    def parse_recipe_detail(self, url: str) -> Optional[Recipe]:
        """解析食谱详情页"""
        logger.info(f"[{self.SOURCE_NAME}] 解析详情: {url}")
        resp = self._fetch_page(url)
        soup = BeautifulSoup(resp.text, "lxml")

        # 标题
        title_el = soup.select_one("h1.page-title")
        if not title_el:
            logger.warning(f"[{self.SOURCE_NAME}] 未找到标题元素")
            return None
        title = title_el.get_text(strip=True)

        # 封面图
        cover_url = ""
        cover_el = soup.select_one("div.cover-image img")
        if cover_el:
            cover_url = cover_el.get("src", "") or cover_el.get("data-src", "")

        # 食材
        ingredients = []
        for row in soup.select("div.ings tr"):
            name_el = row.select_one("td.name")
            weight_el = row.select_one("td.unit")
            if name_el:
                name = name_el.get_text(strip=True)
                weight = weight_el.get_text(strip=True) if weight_el else "适量"
                ingredients.append((name, weight))

        # 步骤
        steps = []
        step_images = []
        for step_el in soup.select("div.steps ol li"):
            text_el = step_el.select_one("p.text")
            img_el = step_el.select_one("img")
            if text_el:
                steps.append(text_el.get_text(strip=True))
            if img_el:
                img_src = img_el.get("src", "") or img_el.get("data-src", "")
                if img_src:
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
        # 检查是否触发了反爬（下厨房可能返回验证页面）
        if "访问验证" in resp.text or "请输入验证码" in resp.text:
            raise RuntimeError(f"[{self.SOURCE_NAME}] 触发反爬验证: {url}")
        return resp
