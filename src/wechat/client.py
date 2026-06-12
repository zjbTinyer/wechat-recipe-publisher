"""
微信公众号 API 客户端
封装 access_token 管理、草稿创建、发布提交
"""
import time
import logging
import requests
from typing import Optional, Dict, Any

from ..utils.retry import retry

logger = logging.getLogger("recipe_publisher")

# 微信 API 基础 URL
API_BASE = "https://api.weixin.qq.com"


class WeChatClient:
    """微信公众号 API 客户端"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # ─── Token 管理 ───────────────────────────────────

    def get_access_token(self) -> str:
        """获取 access_token，内部自动缓存和刷新

        Returns:
            有效的 access_token

        Raises:
            RuntimeError: 获取 token 失败
        """
        # 如果 token 还在有效期内，直接返回（提前 5 分钟刷新）
        if self._access_token and time.time() < (self._token_expires_at - 300):
            return self._access_token

        logger.info("获取微信 access_token...")
        url = f"{API_BASE}/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret,
        }

        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(
                f"获取 access_token 失败: errcode={data.get('errcode')}, "
                f"errmsg={data.get('errmsg')}"
            )

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 7200)
        logger.info(f"access_token 获取成功，有效期 {data.get('expires_in')}s")
        return self._access_token  # type: ignore

    # ─── 素材管理 ───────────────────────────────────

    @retry(max_attempts=3, base_delay=2.0, exceptions=(Exception,))
    def upload_permanent_image(self, image_path: str) -> str:
        """上传永久图片素材（用于文章封面）

        Args:
            image_path: 本地图片文件路径

        Returns:
            media_id（用于草稿的 thumb_media_id）

        Raises:
            RuntimeError: 上传失败
        """
        token = self.get_access_token()
        url = f"{API_BASE}/cgi-bin/material/add_material"
        params = {"access_token": token, "type": "image"}

        logger.info(f"上传永久图片素材: {image_path}")
        with open(image_path, "rb") as f:
            resp = requests.post(
                url, params=params,
                files={"media": f},
                timeout=30,
            )

        data = resp.json()
        if "errcode" in data and data.get("errcode") != 0:
            raise RuntimeError(
                f"上传永久图片失败: errcode={data.get('errcode')}, "
                f"errmsg={data.get('errmsg')}"
            )

        media_id = data.get("media_id", "")
        logger.info(f"永久图片上传成功: media_id={media_id}")
        return media_id

    @retry(max_attempts=3, base_delay=2.0, exceptions=(Exception,))
    def upload_content_image(self, image_path: str) -> str:
        """上传正文图片（不占用素材库额度）

        Args:
            image_path: 本地图片文件路径

        Returns:
            微信 CDN 图片 URL (mmbiz.qpic.cn)，用于 <img src="...">

        Raises:
            RuntimeError: 上传失败
        """
        token = self.get_access_token()
        url = f"{API_BASE}/cgi-bin/media/uploadimg"
        params = {"access_token": token}

        logger.info(f"上传正文图片: {image_path}")
        with open(image_path, "rb") as f:
            resp = requests.post(
                url, params=params,
                files={"media": f},
                timeout=30,
            )

        data = resp.json()
        if "errcode" in data and data.get("errcode") != 0:
            raise RuntimeError(
                f"上传正文图片失败: errcode={data.get('errcode')}, "
                f"errmsg={data.get('errmsg')}"
            )

        img_url = data.get("url", "")
        if not img_url:
            raise RuntimeError("上传正文图片成功但未返回 URL")
        logger.info(f"正文图片上传成功: {img_url[:60]}...")
        return img_url

    # ─── 草稿管理 ───────────────────────────────────

    @retry(max_attempts=3, base_delay=2.0, exceptions=(Exception,))
    def add_draft(self, article: Dict[str, Any]) -> str:
        """创建图文草稿

        Args:
            article: 文章信息字典，包含:
                - title: 标题（最多 64 字符）
                - author: 作者（最多 8 字符）
                - digest: 摘要（最多 120 字符）
                - content: 正文 HTML（最多 20000 字符）
                - content_source_url: 原文链接
                - thumb_media_id: 封面图 media_id

        Returns:
            草稿 media_id
        """
        token = self.get_access_token()
        url = f"{API_BASE}/cgi-bin/draft/add"
        params = {"access_token": token}

        payload = {"articles": [article]}
        logger.info(f"创建草稿: {article.get('title', '')}")

        resp = requests.post(
            url, params=params,
            json=payload,
            timeout=30,
        )

        data = resp.json()
        if "errcode" in data and data.get("errcode") != 0:
            errcode = data.get("errcode")
            errmsg = data.get("errmsg", "")
            raise RuntimeError(
                f"创建草稿失败: errcode={errcode}, errmsg={errmsg}"
            )

        draft_media_id = data.get("media_id", "")
        logger.info(f"草稿创建成功: media_id={draft_media_id}")
        return draft_media_id

    # ─── 发布管理 ───────────────────────────────────

    @retry(max_attempts=3, base_delay=3.0, exceptions=(Exception,))
    def publish(self, draft_media_id: str) -> str:
        """提交发布草稿

        Args:
            draft_media_id: 草稿 media_id（来自 add_draft）

        Returns:
            publish_id（可用于查询发布状态）
        """
        token = self.get_access_token()
        url = f"{API_BASE}/cgi-bin/freepublish/submit"
        params = {"access_token": token}

        payload = {"media_id": draft_media_id}
        logger.info(f"提交发布: media_id={draft_media_id}")

        resp = requests.post(
            url, params=params,
            json=payload,
            timeout=30,
        )

        data = resp.json()
        if "errcode" in data and data.get("errcode") != 0:
            errcode = data.get("errcode")
            errmsg = data.get("errmsg", "")
            raise RuntimeError(
                f"发布失败: errcode={errcode}, errmsg={errmsg}"
            )

        publish_id = data.get("publish_id", "")
        logger.info(f"发布提交成功: publish_id={publish_id}")
        return publish_id

    def get_publish_status(self, publish_id: str) -> Dict[str, Any]:
        """查询发布状态

        Args:
            publish_id: 发布 ID

        Returns:
            发布状态信息
        """
        token = self.get_access_token()
        url = f"{API_BASE}/cgi-bin/freepublish/get"
        params = {"access_token": token}

        resp = requests.post(
            url, params=params,
            json={"publish_id": publish_id},
            timeout=10,
        )

        return resp.json()
