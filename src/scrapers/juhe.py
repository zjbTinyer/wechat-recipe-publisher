"""
聚合数据 (juhe.cn) 菜谱 API 爬虫
免费额度: 100次/天，从海外 IP 可访问，JSON 格式无需 HTML 解析

API 文档: https://www.juhe.cn/docs/api/id/733/aid/1784

注意: 此 API 需要预知菜名来搜索，不返回图片。
"""
import logging
import random
import re
from typing import List, Optional

from .base import BaseScraper, Recipe
from ..utils.retry import retry

logger = logging.getLogger("recipe_publisher")

# 聚合数据 API
JUHE_API_URL = "https://apis.juhe.cn/fapigx/caipu/query"

# 家常菜名称列表（用于随机选取搜索词）
# 覆盖常见菜系，确保 API 每天能返回不同结果
HOME_DISHES = [
    # 猪肉类
    "红烧肉", "回锅肉", "糖醋排骨", "鱼香肉丝", "京酱肉丝",
    "木须肉", "锅包肉", "东坡肉", "梅菜扣肉", "红烧排骨",
    "蒜泥白肉", "粉蒸肉", "宫保肉丁", "酱爆肉丁", "水煮肉片",
    # 鸡肉类
    "宫保鸡丁", "辣子鸡", "黄焖鸡", "白切鸡", "可乐鸡翅",
    "红烧鸡块", "香菇滑鸡", "葱油鸡", "口水鸡", "大盘鸡",
    # 牛肉类
    "西红柿牛腩", "土豆烧牛肉", "孜然牛肉", "黑椒牛柳", "水煮牛肉",
    # 鱼类
    "红烧鱼", "清蒸鲈鱼", "酸菜鱼", "糖醋鱼", "水煮鱼",
    "红烧带鱼", "剁椒鱼头", "松鼠鳜鱼", "茄汁鱼片", "葱烧鲫鱼",
    # 豆腐/蛋类
    "麻婆豆腐", "家常豆腐", "红烧豆腐", "皮蛋豆腐", "虾仁豆腐",
    "番茄炒蛋", "韭菜炒蛋", "虾仁滑蛋", "洋葱炒蛋", "蒸水蛋",
    # 蔬菜类
    "地三鲜", "干煸四季豆", "蒜蓉西兰花", "蚝油生菜", "手撕包菜",
    "醋溜白菜", "清炒时蔬", "干锅花菜", "红烧茄子", "虎皮青椒",
    "酸辣土豆丝", "青椒土豆丝", "炝炒藕片", "蒜蓉粉丝蒸丝瓜", "白灼菜心",
    # 海鲜类
    "油焖大虾", "蒜蓉粉丝蒸虾", "葱姜炒蟹", "辣炒花蛤", "爆炒鱿鱼",
    # 汤类
    "紫菜蛋花汤", "西红柿蛋汤", "酸辣汤", "冬瓜排骨汤", "玉米排骨汤",
    "鲫鱼豆腐汤", "菌菇鸡汤", "萝卜排骨汤", "丝瓜蛋汤", "豆腐青菜汤",
    # 主食
    "蛋炒饭", "扬州炒饭", "番茄意面", "葱油拌面", "炸酱面",
    "青椒肉丝炒饭", "鸡蛋灌饼", "韭菜盒子", "煎饺", "锅贴",
    # 家常小炒
    "青椒肉丝", "芹菜炒香干", "蒜苔炒肉", "尖椒炒蛋", "西葫芦炒鸡蛋",
    "香菇油菜", "蒜苗回锅肉", "豇豆炒肉", "肉末茄子", "蚂蚁上树",
    # 凉菜
    "凉拌黄瓜", "凉拌木耳", "凉拌海带丝", "口水鸡", "蒜泥白肉",
    "凉拌金针菇", "糖拌西红柿", "拍黄瓜", "拌三丝", "红油耳丝",
]

# 额外关键词用于提高多样性
EXTRA_KEYWORDS = [
    "家常", "下饭", "快手", "营养", "简单", "美味", "经典",
]


class JuheScraper(BaseScraper):
    """聚合数据菜谱 API 爬虫（需要 API Key）"""

    SOURCE_NAME = "聚合数据"
    BASE_URL = "https://apis.juhe.cn"

    def __init__(self, api_key: str = ""):
        super().__init__()
        self.api_key = api_key

    def get_recipe_list(self, category: str = "家常菜") -> List[str]:
        """随机选取一个菜名作为搜索词返回"""
        # 随机选 3 个菜名尝试
        candidates = random.sample(HOME_DISHES, min(3, len(HOME_DISHES)))
        return candidates

    def parse_recipe_detail(self, keyword: str) -> Optional[Recipe]:
        """通过菜名关键词查询 API 获取食谱

        Args:
            keyword: 菜名（get_recipe_list 返回的搜索词）

        Returns:
            Recipe 对象
        """
        if not self.api_key:
            logger.error(f"[{self.SOURCE_NAME}] 未配置 API Key (JUHE_API_KEY)")
            return None

        logger.info(f"[{self.SOURCE_NAME}] 查询菜谱: {keyword}")
        data = self._call_api(keyword)
        if not data or not data.get("result"):
            return None

        # 取第一个结果
        results = data["result"]
        if isinstance(results, list):
            item = results[0]
        else:
            item = results

        cp_name = item.get("cp_name", keyword)
        yuanliao = item.get("yuanliao", "")  # 原料
        tiaoliao = item.get("tiaoliao", "")  # 调料
        zuofa = item.get("zuofa", "")        # 做法
        tishi = item.get("tishi", "")        # 提示

        if not zuofa:
            logger.warning(f"[{self.SOURCE_NAME}] 未获取到做法: {cp_name}")
            return None

        # 解析食材（原料 + 调料合并）
        ingredients = []
        if yuanliao:
            ingredients.append(("【主料】", yuanliao))
        if tiaoliao:
            ingredients.append(("【调料】", tiaoliao))

        # 解析步骤（zuofa 通常是 "1.xxx 2.xxx 3.xxx" 格式）
        steps = self._parse_steps(zuofa)

        if tishi:
            steps.append(f"💡 小贴士：{tishi}")

        logger.info(
            f"[{self.SOURCE_NAME}] 解析成功: {cp_name} "
            f"({len(steps)} 步骤)"
        )

        return Recipe(
            title=cp_name,
            cover_image_url="",  # Juhe API 不含图片
            ingredients=ingredients,
            steps=steps,
            step_images=[],
            source_url="https://www.juhe.cn/docs/api/id/733/aid/1784",
        )

    @retry(max_attempts=2, base_delay=1.0, exceptions=(Exception,))
    def _call_api(self, keyword: str) -> dict:
        """调用聚合数据 API"""
        import requests
        params = {
            "key": self.api_key,
            "word": keyword,
            "num": 1,
            "page": 1,
        }
        resp = requests.get(JUHE_API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        error_code = data.get("error_code", -1)
        if error_code != 0:
            error_reason = data.get("reason", "未知错误")
            logger.warning(
                f"[{self.SOURCE_NAME}] API 返回错误: "
                f"error_code={error_code}, reason={error_reason}"
            )
            return {}

        return data

    @staticmethod
    def _parse_steps(zuofa: str) -> List[str]:
        """解析做法文本为步骤列表

        zuofa 格式示例:
        "1.用清水将黄瓜洗净，切成2寸长的段。2.将黄瓜段切成...3...."
        """
        if not zuofa:
            return []

        # 尝试按 "1." "2." 等编号分割
        # 先标准化编号格式
        text = zuofa.strip()

        # 匹配 "1."、"1、"、"步骤1" 等模式
        # 找到所有步骤的分割点
        pattern = r'(?:^|[。；])\s*(\d+)[\.、．)\s]+'
        parts = re.split(pattern, text)

        steps = []
        # re.split 会交替返回 [前缀, 编号1, 内容1, 编号2, 内容2, ...]
        # 跳过第一个前缀（如果有的话），从第一个编号开始
        i = 1
        while i < len(parts) - 1:
            try:
                # parts[i] 是编号, parts[i+1] 是内容
                step_content = parts[i + 1].strip()
                if step_content and len(step_content) >= 3:
                    steps.append(step_content)
            except (ValueError, IndexError):
                pass
            i += 2

        # 如果分割失败，尝试简单按句号分割
        if not steps:
            raw_steps = [s.strip() for s in text.split("。") if s.strip()]
            if len(raw_steps) >= 2:
                steps = raw_steps
            else:
                steps = [text]

        # 清理步骤开头多余的标点
        steps = [re.sub(r'^[\.、,，;；\s]+', '', s) for s in steps]

        return steps

    def get_random_recipe(self, category: str = "家常菜") -> Optional[Recipe]:
        """随机选择一个菜名，通过 API 获取食谱"""
        if not self.api_key:
            logger.error(f"[{self.SOURCE_NAME}] JUHE_API_KEY 未设置，跳过")
            return None

        keywords = self.get_recipe_list(category)
        random.shuffle(keywords)

        for kw in keywords:
            try:
                recipe = self.parse_recipe_detail(kw)
                if recipe and recipe.title and recipe.steps:
                    recipe.source_name = self.SOURCE_NAME
                    return recipe
            except Exception as e:
                logger.warning(f"[{self.SOURCE_NAME}] 查询 '{kw}' 失败: {e}")
                continue

        return None
