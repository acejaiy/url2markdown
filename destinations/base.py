# -*- coding: utf-8 -*-
"""目标适配器基类与导出参数。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fetcher import Article


@dataclass
class ExportOptions:
    """一次抓取任务中，所有目标共用的参数。"""
    local_dir: str = ""
    fmt: str = "Markdown"
    use_category_folder: bool = True
    with_images: bool = True


class BaseDestination:
    """所有导出目标的统一接口。

    高阶用户接入新目标（如思源插件、Obsidian、Notion）时：
    1. 继承 BaseDestination；
    2. 定义 key / label / hint；
    3. 实现 is_ready() 与 export()；
    4. 用 @register 装饰，并在 config.DESTINATION_ORDER 中加入 key。
    """
    key = "base"
    label = "基础目标"
    hint = ""
    available = True

    def __init__(self, settings: Any):
        self.settings = settings

    def is_ready(self) -> tuple[bool, str]:
        """返回 (是否可用, 提示语)。"""
        return True, ""

    def export(self, article: Article, category: str, options: ExportOptions) -> str:
        """导出一篇文章，返回给 GUI 日志展示的一句话。"""
        raise NotImplementedError
