# -*- coding: utf-8 -*-
"""目标适配器注册中心：高阶用户新增导出目标时只需 register 一个子类。"""
from __future__ import annotations

from typing import Any

import config

REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    key = getattr(cls, "key", "")
    if not key:
        raise ValueError("目标适配器必须定义 key")
    REGISTRY[key] = cls
    return cls


def build_destinations(settings: Any) -> dict[str, Any]:
    """按 config.DESTINATION_ORDER 实例化所有已注册目标。"""
    instances = {key: cls(settings) for key, cls in REGISTRY.items()}
    ordered: dict[str, Any] = {}
    for key in config.DESTINATION_ORDER:
        if key in instances:
            ordered[key] = instances.pop(key)
    ordered.update(instances)
    return ordered
