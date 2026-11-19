# -*- coding: utf-8 -*-
"""Obsidian 目标占位：展示扩展入口，正式版启用前不会出现在可勾选目标中。

高阶用户若想提前接入，可按下面三步改造：
1. 把 available 改为 True；
2. 在 is_ready() 中校验 vault 路径；
3. 在 export() 中把 build_markdown(...) 写入 vault，并注册到 config.DESTINATION_ORDER。
"""
from __future__ import annotations

from fetcher import Article

from .base import BaseDestination, ExportOptions
from .registry import register


@register
class ObsidianDestination(BaseDestination):
    key = "obsidian"
    label = "Obsidian（即将支持）"
    hint = "预留入口，暂未开放"
    available = False

    def is_ready(self) -> tuple[bool, str]:
        return False, "即将支持"

    def export(self, article: Article, category: str, options: ExportOptions) -> str:
        raise NotImplementedError("Obsidian 适配器尚未启用，请在 destinations/obsidian.py 中实现。")
