# -*- coding: utf-8 -*-
"""思源笔记写入客户端：通过本地 HTTP API 创建文档、列出目录。

思源内核默认监听 127.0.0.1:6806，本地调用无需 token。
文档路径形如：/政治/文章标题  —— 父级文件夹不存在时思源会自动创建。
"""
from __future__ import annotations

from typing import Optional

import requests

from config import SIYUAN_API, SIYUAN_NOTEBOOK, PATH_PREFIX


class SiYuanClient:
    def __init__(self, api: str = SIYUAN_API, notebook: str = SIYUAN_NOTEBOOK):
        self.api = api.rstrip("/")
        self.notebook_name = notebook
        self._notebook_id: Optional[str] = None

    def _post(self, endpoint: str, payload: dict, timeout: int = 20) -> dict:
        resp = requests.post(f"{self.api}{endpoint}", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def resolve_notebook_id(self) -> str:
        """把笔记本名称解析为 ID，并缓存。找不到时抛出异常。"""
        if self._notebook_id:
            return self._notebook_id
        data = self._post("/api/notebook/lsNotebooks", {})
        notebooks = (data.get("data") or {}).get("notebooks") or []
        for nb in notebooks:
            if nb.get("name") == self.notebook_name:
                self._notebook_id = nb["id"]
                return self._notebook_id
        available = ", ".join(nb.get("name", "?") for nb in notebooks)
        raise RuntimeError(
            f"找不到名为“{self.notebook_name}”的笔记本。现有笔记本：{available}"
        )

    def create_doc(self, path: str, markdown: str) -> str:
        """在指定路径创建 Markdown 文档，返回文档 ID。

        path 需以 / 开头，例如 /政治/关于xxx的意见。
        同名文档已存在时，思源会自动创建并列的新文档（不会覆盖）。
        """
        notebook_id = self.resolve_notebook_id()
        data = self._post(
            "/api/filetree/createDocWithMd",
            {"notebook": notebook_id, "path": path, "markdown": markdown},
            timeout=30,
        )
        if data.get("code") != 0:
            raise RuntimeError(f"思源创建文档失败：{data.get('msg')}（path={path}）")
        return data.get("data") or ""

    def doc_path(self, category: str, title: str) -> str:
        """拼接最终文档路径：前缀 / 分类 / 标题。"""
        segments = [s.strip("/") for s in (PATH_PREFIX, category) if s and s.strip("/")]
        # 标题中不能有路径分隔符，做安全替换
        safe_title = title.replace("/", "／").replace("\\", "＼").strip() or "未命名文章"
        segments.append(safe_title)
        return "/" + "/".join(segments)


if __name__ == "__main__":
    c = SiYuanClient()
    print("笔记本 ID:", c.resolve_notebook_id())
    print("示例路径:", c.doc_path("政治", "关于推动高质量发展的意见"))
