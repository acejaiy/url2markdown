# -*- coding: utf-8 -*-
"""思源笔记目标：把文章 Markdown 直接写入用户指定的笔记本。"""
from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

import config
from fetcher import Article
from md_builder import build_markdown
from siyuan_client import SiYuanClient

from .base import BaseDestination, ExportOptions
from .registry import register


def _ext_from_url(url: str, content_type: str = "") -> str:
    path = urlparse(url).path.lower()
    for ext in ("jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"):
        if path.endswith("." + ext):
            return ".jpg" if ext == "jpeg" else f".{ext}"
    guess = mimetypes.guess_extension((content_type or "").split(";")[0])
    return guess or ".jpg"


@register
class SiYuanDestination(BaseDestination):
    key = "siyuan"
    label = "剪藏至思源笔记"
    hint = "首次使用点右侧「更改思源笔记配置」，以后无需再填"

    def _client(self) -> SiYuanClient:
        cfg = self.settings.get("siyuan", {}) or {}
        return SiYuanClient(
            api_base=cfg.get("api_base", config.SIYUAN_API_BASE),
            notebook_id=cfg.get("notebook_id", ""),
            token=cfg.get("token", ""),
            path_prefix=cfg.get("path_prefix", config.SIYUAN_PATH_PREFIX),
            timeout=cfg.get("timeout", config.SIYUAN_TIMEOUT),
        )

    def is_ready(self) -> tuple[bool, str]:
        cfg = self.settings.get("siyuan", {}) or {}
        if not cfg.get("api_base"):
            return False, "请先设置思源 API 地址"
        if not cfg.get("notebook_id"):
            return False, "请先在配置窗口点「测试连接」并选中笔记本"
        return True, ""

    def _image_map(self, client: SiYuanClient, article: Article,
                   with_images: bool) -> dict[int, str]:
        """返回 [[IMG:n]] -> 思源可用的图片地址。默认用原图 URL，最稳。"""
        if not with_images or not article.images:
            return {}
        result = {i: url for i, url in enumerate(article.images)}

        if not config.SIYUAN_UPLOAD_IMAGES:
            return result

        # 实验性：上传为思源资产。失败则静默回退到原图 URL。
        try:
            items: list[tuple[str, bytes]] = []
            indices: list[int] = []
            for idx, url in enumerate(article.images):
                resp = requests.get(
                    url,
                    headers={"User-Agent": config.USER_AGENT, "Referer": article.url},
                    timeout=config.REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                if len(resp.content) < 100:
                    continue
                ext = _ext_from_url(url, resp.headers.get("Content-Type", ""))
                items.append((f"web-clip-{idx + 1:02d}{ext}", resp.content))
                indices.append(idx)
            paths = client.upload_assets(items)
            for idx, path in zip(indices, paths):
                result[idx] = path
        except Exception:
            pass
        return result

    def export(self, article: Article, category: str, options: ExportOptions) -> str:
        client = self._client()
        img_map = self._image_map(client, article, options.with_images)
        markdown = build_markdown(article, category, img_map)

        title = article.title
        if config.SIYUAN_ADD_TIME_SUFFIX:
            title = f"{title}_{datetime.now():%Y%m%d-%H%M%S}"

        doc_id, path = client.create_doc(category, title, markdown)
        return f"已剪藏至思源：{path}" + (f"（文档 ID：{doc_id}）" if doc_id else "")
