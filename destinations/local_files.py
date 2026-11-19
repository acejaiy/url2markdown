# -*- coding: utf-8 -*-
"""本地文件目标：复用旧版 saver，保证 V1.1.0 不改动原有导出逻辑。"""
from __future__ import annotations

from fetcher import Article
from saver import save_article
from settings import default_desktop_dir

from .base import BaseDestination, ExportOptions
from .registry import register


@register
class LocalFilesDestination(BaseDestination):
    key = "local"
    label = "保存为本地文件"
    hint = "Markdown / TXT / Word，图片下载到 assets"

    def is_ready(self) -> tuple[bool, str]:
        target = self.settings.get("local.dir", "") or default_desktop_dir()
        if not target:
            return False, "请先选择保存位置"
        return True, ""

    def export(self, article: Article, category: str, options: ExportOptions) -> str:
        target = options.local_dir or self.settings.get("local.dir", "") or default_desktop_dir()
        path = save_article(
            article,
            category,
            target,
            options.fmt,
            options.use_category_folder,
            options.with_images,
        )
        return f"本地文件已保存：{path}"
