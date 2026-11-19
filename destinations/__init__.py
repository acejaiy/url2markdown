# -*- coding: utf-8 -*-
"""导出目标适配器包：local / siyuan / obsidian(预留)。"""
from .base import BaseDestination, ExportOptions
from .registry import REGISTRY, build_destinations, register

# 导入即注册
from . import local_files  # noqa: F401
from . import siyuan  # noqa: F401
from . import obsidian  # noqa: F401

__all__ = [
    "BaseDestination",
    "ExportOptions",
    "REGISTRY",
    "register",
    "build_destinations",
    "local_files",
    "siyuan",
    "obsidian",
]
