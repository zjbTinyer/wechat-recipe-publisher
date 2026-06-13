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
        """解析食谱详情页

        页面结构 (从 GitHub Actions 诊断确认):
        - 步骤: div.recipeStep_word (每个 div 一步)
        - 食材: div.subtitle (纯文本，需解析)
        - 标题: h1 或 div.detail 内的标题
        """
        logger.info(f"[{self.SOURCE_NAME}] 解析详情: {url}")
        resp = self._fetch_page(url)
        # 强制设置编码为 UTF-8
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        # ── 标题 ──
        title_el = soup.select_one(
            "h1#recipe_title, h1.recipe_De_title, "
            "div.detail h1, div.recipe-title h1, h1"
        )
        if not title_el:
            logger.warning(f"[{self.SOURCE_NAME}] 未找到标题元素")
            return None
        title = title_el.get_text(strip=True)

        # ── 封面图 ──
        cover_url = ""
        for sel in [
            "div.recipe_cover img#recipe_img",
            "div.recipe_cover img",
            "div.detail img",
            "div.recipe-show img",
        ]:
            cover_el = soup.select_one(sel)
            if cover_el:
                cover_url = cover_el.get("data-src", "") or cover_el.get("src", "")
                if cover_url and "logo" not in cover_url:
                    break

        # ── 食材 ──
        # 从天诊断来看食材在 div.subtitle 中，格式如"辅食油菜2颗纯净水适量"
        ingredients = []
        subtitle = soup.select_one("div.subtitle")
        if subtitle:
            ingredient_text = subtitle.get_text(strip=True)
            # 尝试按食材+用量模式拆分
            # 常见的模式：食材名+数字/量词
            import re
            # 匹配"XX N颗/个/g/克/勺/适量"等模式
            pattern = r'([^\d\s]+?)(\d+[颗个克gG升毫mMlL勺只条根片块]+\b|[适量少许]+)'
            matches = re.findall(pattern, ingredient_text)
            if matches:
                for name, weight in matches:
                    ingredients.append((name.strip(), weight.strip()))
            # 如果正则匹配不到，按空格拆分当作列表
            if not ingredients and ingredient_text:
                parts = ingredient_text.replace("，", " ").replace(",", " ").split()
                for part in parts:
                    if part and len(part) > 1:
                        ingredients.append((part, "适量"))
            if ingredients:
                logger.info(f"[{self.SOURCE_NAME}] 从 subtitle 解析到 {len(ingredients)} 种食材")

        # 备选：从 mbox 中找食材
        if not ingredients:
            for mbox in soup.select("div.mbox"):
                text = mbox.get_text(strip=True)
                if any(kw in text for kw in ["食材", "主料", "配料", "调料"]):
                    # 简单提取
                    lines = [l.strip() for l in text.split() if l.strip() and len(l.strip()) > 2]
                    for line in lines[:20]:
                        if line and len(line) < 50:
                            ingredients.append((line, "适量"))
                    if ingredients:
                        break

        # ── 步骤 ──
        # 从诊断确认: div.recipeStep_word 包含每一步
        steps = []
        step_images = []
        step_words = soup.select("div.recipeStep_word")
        if step_words:
            logger.info(f"[{self.SOURCE_NAME}] 步骤选择器匹配: div.recipeStep_word ({len(step_words)} 项)")
            for sw in step_words:
                text = sw.get_text(strip=True)
                if text and len(text) > 3:
                    steps.append(text)
                img = sw.select_one("img")
                if img:
                    img_src = img.get("data-src", "") or img.get("src", "")
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
