"""
图片处理模块
负责下载远程图片、验证格式/大小、重命名保存
"""
import os
import uuid
import logging
import requests
from typing import Optional, List
from urllib.parse import urlparse

from ..utils.retry import retry

logger = logging.getLogger("recipe_publisher")

# 允许的图片格式
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}
# 最大文件大小 (10MB for 永久素材, 1MB for 内容图片)
MAX_PERMANENT_SIZE = 10 * 1024 * 1024   # 10MB
MAX_CONTENT_SIZE = 1 * 1024 * 1024      # 1MB


def get_extension_from_url(url: str) -> str:
    """从 URL 提取文件扩展名（去除参数）"""
    parsed = urlparse(url)
    path = parsed.path
    ext = os.path.splitext(path)[1].lower()
    # 去除可能的后缀参数
    if "?" in ext:
        ext = ext.split("?")[0]
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"  # 默认
    return ext


@retry(max_attempts=2, base_delay=1.0, exceptions=(Exception,))
def download_image(url: str, save_dir: str, referer: str = "",
                   prefix: str = "img") -> Optional[str]:
    """下载图片到本地

    Args:
        url: 图片 URL
        save_dir: 保存目录
        referer: Referer 头（绕过防盗链）
        prefix: 文件名前缀

    Returns:
        本地文件路径，失败返回 None
    """
    if not url:
        return None

    os.makedirs(save_dir, exist_ok=True)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    }
    if referer:
        headers["Referer"] = referer

    try:
        logger.info(f"下载图片: {url[:80]}...")
        resp = requests.get(url, headers=headers, timeout=20, stream=True)
        resp.raise_for_status()

        # 检查 Content-Type
        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type and content_type:
            logger.warning(f"非图片响应 Content-Type={content_type}: {url[:60]}")
            return None

        ext = get_extension_from_url(url)
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}{ext}"
        filepath = os.path.join(save_dir, filename)

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # 检查文件大小
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            os.remove(filepath)
            logger.warning("下载的图片为空")
            return None

        logger.info(f"图片已保存: {filepath} ({file_size} bytes)")
        return filepath

    except Exception as e:
        logger.error(f"下载图片失败: {e}")
        return None


def process_images_for_article(
    recipe_images: List[str],
    wechat_client,
    save_dir: str,
    source_base_url: str = "",
) -> List[str]:
    """批量处理文章图片：下载 → 上传微信 CDN → 返回 CDN URL

    Args:
        recipe_images: 食谱图片 URL 列表
        wechat_client: WeChatClient 实例
        save_dir: 临时保存目录
        source_base_url: 来源网站基础 URL（用于 Referer）

    Returns:
        微信 CDN 图片 URL 列表
    """
    wx_urls = []

    for i, img_url in enumerate(recipe_images):
        if not img_url:
            wx_urls.append("")
            continue

        # 下载图片
        local_path = download_image(
            img_url, save_dir,
            referer=source_base_url,
            prefix=f"step{i+1}",
        )
        if not local_path:
            wx_urls.append("")
            continue

        # 上传到微信
        try:
            wx_url = wechat_client.upload_content_image(local_path)
            wx_urls.append(wx_url)
        except Exception as e:
            logger.error(f"上传内容图片到微信失败: {e}")
            wx_urls.append("")
        finally:
            # 清理临时图片
            try:
                os.remove(local_path)
            except OSError:
                pass

    return wx_urls
