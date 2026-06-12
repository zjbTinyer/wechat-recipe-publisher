"""
每日家常菜公众号自动发布 — 主入口
编排完整流程：抓取食谱 → 处理图片 → 构建文章 → 发布到公众号
"""
import os
import sys
import logging
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Config
from src.utils.logger import setup_logger
from src.scrapers import fetch_recipe
from src.wechat.client import WeChatClient
from src.wechat.image import download_image, process_images_for_article
from src.wechat.article import build_article_html, build_draft_payload


def main():
    """主流程"""
    # ── 1. 加载配置 ────────────────────────────────
    config = Config.from_env()
    logger = setup_logger(config.log_level)

    logger.info("=" * 50)
    logger.info("每日家常菜公众号自动发布 - 开始运行")
    logger.info("=" * 50)
    logger.info(f"配置: 首选爬虫={config.primary_scraper}, "
                f"分类={config.recipe_category}")

    # 确保临时目录存在
    os.makedirs(config.recipes_dir, exist_ok=True)

    # ── 2. 抓取食谱 ────────────────────────────────
    logger.info(">>> 第1步: 抓取食谱")
    try:
        recipe = fetch_recipe(
            primary=config.primary_scraper,
            category=config.recipe_category,
            juhe_api_key=config.juhe_api_key,
        )
    except Exception as e:
        logger.error(f"抓取食谱失败: {e}")
        sys.exit(1)

    logger.info(f"食谱: {recipe.title}")
    logger.info(f"来源: {recipe.source_name} ({recipe.source_url})")
    logger.info(f"食材: {len(recipe.ingredients)} 种")
    logger.info(f"步骤: {len(recipe.steps)} 步")
    logger.info(f"步骤图片: {len(recipe.step_images)} 张")

    # ── 3. 初始化微信客户端 ─────────────────────────
    logger.info(">>> 第2步: 连接微信公众号")
    try:
        wechat = WeChatClient(
            app_id=config.wechat_app_id,
            app_secret=config.wechat_app_secret,
        )
        # 预获取 token 验证凭证
        wechat.get_access_token()
        logger.info("微信 access_token 获取成功")
    except Exception as e:
        logger.error(f"微信连接失败: {e}")
        sys.exit(1)

    # ── 4. 处理图片 ────────────────────────────────
    logger.info(">>> 第3步: 处理图片")

    # 4.1 封面图：下载 → 上传永久素材 → 获取 media_id
    thumb_media_id = ""
    if recipe.cover_image_url:
        logger.info("处理封面图...")
        cover_path = download_image(
            recipe.cover_image_url,
            config.recipes_dir,
            referer=recipe.source_url,
            prefix="cover",
        )
        if cover_path:
            try:
                thumb_media_id = wechat.upload_permanent_image(cover_path)
                logger.info(f"封面图 media_id: {thumb_media_id}")
            except Exception as e:
                logger.error(f"上传封面图失败: {e}")
            finally:
                # 不再需要本地文件（永久素材不需要在正文中引用本地文件）
                try:
                    os.remove(cover_path)
                except OSError:
                    pass

    # 4.2 内容图片：下载 → 上传微信 CDN → 获取 mmbiz 域名 URL
    step_wx_urls = []
    if recipe.step_images:
        logger.info(f"处理 {len(recipe.step_images)} 张步骤图片...")
        step_wx_urls = process_images_for_article(
            recipe.step_images,
            wechat,
            config.recipes_dir,
            source_base_url=recipe.source_url,
        )
        success_count = sum(1 for u in step_wx_urls if u)
        logger.info(f"步骤图片上传成功: {success_count}/{len(recipe.step_images)}")

    # 封面图正文内的展示用图（重新上传为内容图片）
    cover_wx_url = ""
    if recipe.cover_image_url:
        cover_content_path = download_image(
            recipe.cover_image_url,
            config.recipes_dir,
            referer=recipe.source_url,
            prefix="cover_content",
        )
        if cover_content_path:
            try:
                cover_wx_url = wechat.upload_content_image(cover_content_path)
            except Exception as e:
                logger.error(f"上传封面内容图失败: {e}")
            finally:
                try:
                    os.remove(cover_content_path)
                except OSError:
                    pass

    # ── 5. 构建文章 HTML ───────────────────────────
    logger.info(">>> 第4步: 构建文章 HTML")
    html_content = build_article_html(recipe, cover_wx_url, step_wx_urls)
    logger.info(f"文章 HTML 长度: {len(html_content)} 字符")

    # ── 6. 创建草稿 ────────────────────────────────
    logger.info(">>> 第5步: 创建草稿")
    draft_payload = build_draft_payload(
        recipe,
        html_content,
        thumb_media_id,
        author_name=config.author_name,
    )
    logger.info(f"草稿标题: {draft_payload['title']}")
    logger.info(f"草稿摘要: {draft_payload['digest'][:60]}...")

    try:
        draft_media_id = wechat.add_draft(draft_payload)
    except Exception as e:
        logger.error(f"创建草稿失败: {e}")
        sys.exit(1)

    # ── 7. 提交发布 ────────────────────────────────
    logger.info(">>> 第6步: 提交发布")
    try:
        publish_id = wechat.publish(draft_media_id)
        logger.info("=" * 50)
        logger.info(f"✅ 发布成功！")
        logger.info(f"   菜名: {recipe.title}")
        logger.info(f"   来源: {recipe.source_name}")
        logger.info(f"   原文: {recipe.source_url}")
        logger.info(f"   publish_id: {publish_id}")
        logger.info("=" * 50)
    except Exception as e:
        logger.error(f"发布失败: {e}")
        logger.info(f"草稿已创建，media_id={draft_media_id}，可手动发布")
        sys.exit(1)

    logger.info("每日家常菜公众号自动发布 - 运行完成")


if __name__ == "__main__":
    main()
