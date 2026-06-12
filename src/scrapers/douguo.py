"""
豆果美食 (douguo.com) 爬虫
实测可用——作为首选爬虫源
页面结构 (2026-06 实测):
- 列表: ul#jxlist li a → /cookbook/{id}.html
- 标题: h1
- 封面: #banner img
- 食材: div.metarial → tr → td (span.scname + span.scnum)
- 步骤: div.stepcont → div.stepinfo (文字) + img (图片)
"""
import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Recipe
from ..utils.retry import retry

logger = logging.getLogger("recipe_publisher")


class DouguoScraper(BaseScraper):
    """豆果美食爬虫 (实测稳定可用)"""

    SOURCE_NAME = "豆果美食"
    BASE_URL = "https://www.douguo.com"

    # 多个列表页作为备选
    LIST_URLS = [
        "/jingxuan/0",          # 精选
    ]

    def get_recipe_list(self, category: str = "家常菜") -> List[str]:
        """从精选列表页获取食谱链接"""
        urls = []

        for list_path in self.LIST_URLS:
            list_url = f"{self.BASE_URL}{list_path}"
            logger.info(f"[{self.SOURCE_NAME}] 请求列表页: {list_url}")
            try:
                resp = self._fetch_page(list_url)
            except Exception as e:
                logger.warning(f"[{self.SOURCE_NAME}] 列表页请求失败: {e}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # 列表项中的食谱链接: ul#jxlist li a
            for item in soup.select("ul#jxlist li a"):
                href = item.get("href", "")
                if href and "/cookbook/" in href:
                    full_url = urljoin(self.BASE_URL, href)
                    if full_url not in urls and full_url.endswith(".html"):
                        urls.append(full_url)

            if urls:
                break

        return urls

    def parse_recipe_detail(self, url: str) -> Optional[Recipe]:
        """解析食谱详情页"""
        logger.info(f"[{self.SOURCE_NAME}] 解析详情: {url}")
        resp = self._fetch_page(url)
        soup = BeautifulSoup(resp.text, "lxml")

        # ── 标题 ──
        title_el = soup.select_one("h1")
        if not title_el:
            logger.warning(f"[{self.SOURCE_NAME}] 未找到标题元素")
            return None
        title = title_el.get_text(strip=True)

        # ── 封面图 ──
        cover_url = ""
        cover_el = soup.select_one("#banner img")
        if cover_el:
            cover_url = cover_el.get("src", "") or cover_el.get("data-src", "")

        # ── 食材 ──
        # 豆果食材在 div.metarial 中，每个 tr 是一行
        # span.scname = 名称, span.scnum = 用量
        # 注意: 一行可能包含多个食材（每行最多 2 对 name+num）
        ingredients = []
        metarial = soup.select_one("div.metarial")
        if metarial:
            for tr in metarial.select("tr"):
                names = tr.select("span.scname")
                weights = tr.select("span.scnum")
                for i, name_el in enumerate(names):
                    name = name_el.get_text(strip=True)
                    if not name:
                        continue
                    # 对应的用量（索引匹配）
                    weight = weights[i].get_text(strip=True) if i < len(weights) else "适量"
                    # 跳过明显不是食材的内容
                    if any(kw in name for kw in ["配方", "做法", "步骤"]):
                        continue
                    ingredients.append((name, weight))

        # ── 步骤 ──
        # 步骤在 div.stepcont 中
        # div.stepinfo = 文字描述, img = 步骤图片
        steps = []
        step_images = []

        for stepcont in soup.select("div.stepcont"):
            # 文字
            stepinfo = stepcont.select_one("div.stepinfo")
            if stepinfo:
                text = stepinfo.get_text(strip=True)
                # 去除开头的"步骤N"前缀
                text = re.sub(r'^步骤\d+', '', text).strip()
                if text:
                    steps.append(text)

            # 图片
            img = stepcont.select_one("img")
            if img:
                img_src = img.get("src", "") or img.get("data-src", "")
                if img_src:
                    step_images.append(img_src)

        if not steps:
            logger.warning(f"[{self.SOURCE_NAME}] 未找到步骤")
            return None

        logger.info(f"[{self.SOURCE_NAME}] 解析成功: {title} "
                    f"({len(ingredients)}食材, {len(steps)}步骤, "
                    f"{len(step_images)}图片)")

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
        resp = self.session.get(url, timeout=20)
        resp.raise_for_status()
        return resp
