# -*- coding: utf-8 -*-
"""本机配置持久化：GUI 中设置一次，后续自动记住。

配置文件位置（不会写进仓库，便于 exe 在只读目录也能运行）：
- Windows: %APPDATA%/url2markdown-preview/settings.json
- 其他系统: ~/.config/url2markdown-preview/settings.json（或用户主目录）
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import config


def default_desktop_dir() -> str:
    """返回系统桌面路径，兼容中文「桌面」。"""
    home = Path(os.path.expanduser("~"))
    for name in ("Desktop", "桌面"):
        p = home / name
        if p.exists():
            return str(p)
    return str(home)


def default_settings_path() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "url2markdown-preview" / "settings.json"
    return Path.home() / ".config" / "url2markdown-preview" / "settings.json"


DEFAULT_SETTINGS: dict[str, Any] = {
    "schema_version": 1,
    "local": {
        "dir": default_desktop_dir(),
        "format": config.DEFAULT_FORMAT,
        "use_category_folder": config.DEFAULT_USE_CATEGORY_FOLDER,
        "with_images": config.DEFAULT_WITH_IMAGES,
    },
    "siyuan": {
        "api_base": config.SIYUAN_API_BASE,
        "notebook_id": config.SIYUAN_NOTEBOOK_ID,
        "token": config.SIYUAN_TOKEN,
        "path_prefix": config.SIYUAN_PATH_PREFIX,
        "timeout": config.SIYUAN_TIMEOUT,
    },
    "destinations": {
        "local": config.DEFAULT_LOCAL_TARGET,
        "siyuan": config.DEFAULT_SIYUAN_TARGET,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class Settings:
    """带默认值合并的 JSON 配置。"""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_settings_path()
        self.data: dict[str, Any] = _deep_merge(DEFAULT_SETTINGS, {})
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data = _deep_merge(self.data, loaded)
        except Exception:
            # 配置损坏时回退默认值，不让 GUI 启动失败
            self.data = _deep_merge(DEFAULT_SETTINGS, {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, dotted_key: str, default: Any = None) -> Any:
        cur: Any = self.data
        for part in dotted_key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, dotted_key: str, value: Any) -> None:
        parts = dotted_key.split(".")
        cur = self.data
        for part in parts[:-1]:
            if not isinstance(cur.get(part), dict):
                cur[part] = {}
            cur = cur[part]
        cur[parts[-1]] = value


if __name__ == "__main__":
    s = Settings()
    print("配置文件:", s.path)
    print("当前配置:", json.dumps(s.data, ensure_ascii=False, indent=2))
