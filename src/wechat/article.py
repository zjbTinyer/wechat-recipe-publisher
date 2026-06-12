"""
文章 HTML 模板构建器
将 Recipe 数据渲染为微信公众号兼容的富文本 HTML
"""
import html
import logging
from typing import List, Tuple, Optional

from ..scrapers.base import Recipe

logger = logging.getLogger("recipe_publisher")

# 微信 content 字段最大字符数
MAX_CONTENT_LENGTH = 20000

# 颜色主题
COLOR_PRIMARY = "#c0392b"       # 主色（红色系）
COLOR_BG_CARD = "#fafafa"       # 卡片背景
COLOR_BG_INTRO = "#f8f8f8"      # 引言背景
COLOR_TEXT = "#333333"          # 正文文字
COLOR_TEXT_LIGHT = "#999999"    # 浅色文字
COLOR_TABLE_HEADER = "#f5f5f5"  # 表头背景


def build_article_html(
    recipe: Recipe,
    cover_wx_url: str = "",
    step_wx_urls: Optional[List[str]] = None,
) -> str:
    """根据食谱数据构建文章 HTML

    Args:
        recipe: Recipe 对象
        cover_wx_url: 封面图的微信 CDN URL（用于正文内展示）
        step_wx_urls: 步骤图片的微信 CDN URL 列表

    Returns:
        符合微信限制的 HTML 字符串
    """
    if step_wx_urls is None:
        step_wx_urls = []

    parts: List[str] = []

    # ─── 头部 ───────────────────────────────────────
    parts.append(f"""
<div style="max-width:100%;overflow-x:hidden;">

<!-- 封面图 -->
""")
    if cover_wx_url:
        parts.append(f"""
<div style="text-align:center;margin-bottom:20px;">
  <img src="{html.escape(cover_wx_url)}" style="width:100%;display:block;border-radius:8px;" alt="{html.escape(recipe.title)}">
</div>
""")

    # ─── 菜名标题 ───────────────────────────────────
    parts.append(f"""
<h1 style="font-size:22px;color:{COLOR_PRIMARY};text-align:center;margin:20px 0;font-weight:bold;">
  {html.escape(recipe.title)}
</h1>
""")

    # ─── 引言 ───────────────────────────────────────
    parts.append(f"""
<section style="background:{COLOR_BG_INTRO};padding:15px;border-radius:8px;margin-bottom:20px;">
  <p style="font-size:15px;color:{COLOR_TEXT};line-height:1.8;margin:0;text-indent:2em;">
    {html.escape(recipe.summary)}
  </p>
</section>
""")

    # ─── 食材准备 ───────────────────────────────────
    if recipe.ingredients:
        parts.append(f"""
<h2 style="font-size:18px;color:{COLOR_PRIMARY};border-left:4px solid {COLOR_PRIMARY};padding-left:10px;margin:25px 0 15px;">
  📋 食材准备
</h2>
<table style="width:100%;border-collapse:collapse;margin-bottom:20px;font-size:14px;">
  <tr style="background:{COLOR_TABLE_HEADER};font-weight:bold;">
    <td style="padding:10px 12px;border-bottom:1px solid #eee;color:{COLOR_TEXT};">食材</td>
    <td style="padding:10px 12px;border-bottom:1px solid #eee;color:{COLOR_TEXT};text-align:right;">用量</td>
  </tr>
""")
        for i, (name, weight) in enumerate(recipe.ingredients):
            bg = "transparent" if i % 2 == 0 else "#fafafa"
            parts.append(f"""
  <tr style="background:{bg};">
    <td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;">{html.escape(name)}</td>
    <td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;text-align:right;color:#666;">{html.escape(weight)}</td>
  </tr>
""")
        parts.append("</table>")

    # ─── 烹饪步骤 ───────────────────────────────────
    parts.append(f"""
<h2 style="font-size:18px;color:{COLOR_PRIMARY};border-left:4px solid {COLOR_PRIMARY};padding-left:10px;margin:25px 0 15px;">
  🍳 烹饪步骤
</h2>
""")

    for i, step_text in enumerate(recipe.steps):
        step_num = i + 1
        parts.append(f"""
<div style="margin-bottom:20px;padding:15px;background:{COLOR_BG_CARD};border-radius:8px;">
  <div style="display:flex;align-items:flex-start;margin-bottom:8px;">
    <span style="
      display:inline-flex;align-items:center;justify-content:center;
      min-width:28px;height:28px;line-height:28px;
      background:{COLOR_PRIMARY};color:#fff;border-radius:50%;
      font-size:14px;font-weight:bold;margin-right:12px;flex-shrink:0;
    ">{step_num}</span>
    <span style="font-size:15px;color:{COLOR_TEXT};line-height:1.8;flex:1;">
      {html.escape(step_text)}
    </span>
  </div>
""")
        # 步骤图片（如果有）
        if i < len(step_wx_urls) and step_wx_urls[i]:
            parts.append(f"""
  <img src="{html.escape(step_wx_urls[i])}" style="width:100%;margin-top:10px;border-radius:6px;display:block;" alt="步骤{step_num}">
""")
        parts.append("</div>")

    # ─── 小贴士 ─────────────────────────────────────
    parts.append(f"""
<h2 style="font-size:18px;color:{COLOR_PRIMARY};border-left:4px solid {COLOR_PRIMARY};padding-left:10px;margin:25px 0 15px;">
  💡 小贴士
</h2>
<section style="background:{COLOR_BG_INTRO};padding:15px;border-radius:8px;margin-bottom:20px;">
  <p style="font-size:14px;color:{COLOR_TEXT};line-height:1.8;margin:0;">
    1. 做菜前先把所有食材准备好，避免手忙脚乱。<br>
    2. 调味品的用量可以根据个人口味适量调整。<br>
    3. 如果喜欢，可以在最后撒上一些葱花或香菜提香。<br>
    4. 趁热食用口感最佳！
  </p>
</section>
""")

    # ─── 页脚 ───────────────────────────────────────
    parts.append(f"""
<hr style="border:none;border-top:1px solid #eee;margin:30px 0 15px;">
<p style="text-align:center;color:{COLOR_TEXT_LIGHT};font-size:13px;margin:10px 0;">
  本文由「每日家常菜」自动整理
</p>
""")
    if recipe.source_url:
        parts.append(f"""
<p style="text-align:center;color:{COLOR_TEXT_LIGHT};font-size:12px;margin:5px 0;">
  食谱参考：<a href="{html.escape(recipe.source_url)}" style="color:{COLOR_TEXT_LIGHT};text-decoration:none;">{html.escape(recipe.source_name)}</a>
</p>
""")
    parts.append("""
<p style="text-align:center;color:{COLOR_TEXT_LIGHT};font-size:12px;margin:5px 0 20px;">
  每天一道家常菜，让餐桌更有温度 ❤️
</p>
</div>
""")

    html_content = "".join(parts)

    # 检查长度
    if len(html_content) > MAX_CONTENT_LENGTH:
        logger.warning(
            f"文章 HTML 长度 {len(html_content)} 超过微信限制 {MAX_CONTENT_LENGTH}，进行截断"
        )
        # 简单截断（保留结构完整性）
        html_content = html_content[:MAX_CONTENT_LENGTH - 200] + """
<p style="text-align:center;color:{COLOR_TEXT_LIGHT};font-size:12px;">（内容有删减）</p>
</div>"""

    return html_content


def build_draft_payload(
    recipe: Recipe,
    html_content: str,
    thumb_media_id: str,
    author_name: str = "每日家常菜",
) -> dict:
    """构建创建草稿的请求体

    Args:
        recipe: Recipe 对象
        html_content: 文章 HTML
        thumb_media_id: 封面图 media_id
        author_name: 作者名称

    Returns:
        API 请求体字典
    """
    # 标题不超过 64 字符
    title = recipe.title
    if len(title) > 64:
        title = title[:61] + "..."

    # 摘要不超过 120 字符
    digest = recipe.summary
    if len(digest) > 120:
        digest = digest[:117] + "..."

    return {
        "title": title,
        "author": author_name[:8],  # 最多 8 个字符
        "digest": digest,
        "content": html_content,
        "content_source_url": recipe.source_url or "",
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
    }
