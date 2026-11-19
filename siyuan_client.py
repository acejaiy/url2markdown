# -*- coding: utf-8 -*-
"""思源笔记 HTTP API 客户端（V1.1.0 GUI 使用）。

设计目标：
- 小白：在 GUI 里点「测试连接」自动列出笔记本，下拉选中即可（无需手动找 ID）；
- 高阶：可传 token、自定义 path_prefix、超时，也可在 destinations/siyuan.py 中替换实现。

常用接口：
- /api/notebook/lsNotebooks          列出笔记本（用于测试连接）
- /api/filetree/createDocWithMd      在笔记本指定路径创建 Markdown 文档
"""
from __future__ import annotations

import mimetypes
import re
from typing import Iterable

import requests

import config


def normalize_api_base(value: str) -> str:
    """把用户输入的 127.0.0.1:6806 / http://.../ 统一成 http://127.0.0.1:6806。"""
    s = (value or "").strip().rstrip("/")
    if not s:
        return config.SIYUAN_API_BASE
    if not s.lower().startswith(("http://", "https://")):
        s = "http://" + s
    if s.lower().endswith("/api"):
        s = s[:-4]
    return s


class SiYuanClient:
    def __init__(self, api_base: str = config.SIYUAN_API_BASE,
                 notebook_id: str = "", token: str = "",
                 path_prefix: str = config.SIYUAN_PATH_PREFIX,
                 timeout: int = config.SIYUAN_TIMEOUT):
        self.api_base = normalize_api_base(api_base)
        self.notebook_id = (notebook_id or "").strip()
        self.token = (token or "").strip()
        self.path_prefix = (path_prefix or "").strip()
        self.timeout = int(timeout or config.SIYUAN_TIMEOUT)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        return headers

    def _post(self, endpoint: str, payload: dict | None = None,
              timeout: int | None = None) -> dict:
        url = f"{self.api_base}{endpoint}"
        resp = requests.post(
            url, json=payload or {}, headers=self._headers(),
            timeout=timeout or self.timeout,
        )
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError(f"思源接口返回的不是 JSON：{resp.text[:120]}") from exc
        if isinstance(data, dict):
            code = data.get("code")
            if code is not None and int(code) != 0:
                raise RuntimeError(f"思源接口错误 {code}：{data.get('msg') or data}")
            return data
        raise RuntimeError(f"思源接口返回格式异常：{str(data)[:120]}")

    def list_notebooks(self) -> list[dict]:
        data = self._post("/api/notebook/lsNotebooks", {})
        payload = data.get("data") or {}
        notebooks = payload.get("notebooks") if isinstance(payload, dict) else None
        return notebooks if isinstance(notebooks, list) else []

    def notebook_name(self) -> str:
        """返回已配置笔记本 ID 对应的名称，找不到时返回空串。"""
        if not self.notebook_id:
            return ""
        for nb in self.list_notebooks():
            if str(nb.get("id", "")) == self.notebook_id:
                return str(nb.get("name") or "")
        return ""

    def test_connection(self) -> tuple[bool, str]:
        """供 GUI「测试连接」按钮调用。"""
        try:
            notebooks = self.list_notebooks()
        except Exception as exc:
            return False, f"连接失败：{exc}\n请确认思源已启动，且 API 地址正确。"
        names = [str(nb.get("name") or "未命名") for nb in notebooks]
        if not self.notebook_id:
            return True, (
                f"连接成功，共发现 {len(notebooks)} 个笔记本：\n"
                + ("、".join(names[:20]) or "（暂无笔记本）")
                + "\n\n请在 GUI 中点「测试连接」后从列表选中笔记本，或勾选「手动填 ID」粘贴。"
            )
        name = self.notebook_name()
        if not name:
            return False, (
                "连接成功，但当前选中的笔记本 ID 已失效。\n"
                "请在 GUI 中重新点「测试连接」，从列表重新选中笔记本。\n"
                "现有笔记本：" + ("、".join(names[:20]) or "（暂无）")
            )
        return True, f"连接成功！目标笔记本：{name}（共 {len(notebooks)} 个笔记本）"

    @staticmethod
    def _safe_segment(value: str) -> str:
        return (
            (value or "")
            .replace("/", "／")
            .replace("\\", "＼")
            .replace("\r", " ")
            .replace("\n", " ")
            .strip() or "未命名"
        )

    def doc_path(self, category: str, title: str) -> str:
        """拼接思源文档路径：/前缀/分类/标题。"""
        segments: list[str] = []
        for part in (self.path_prefix, category):
            part = (part or "").strip().strip("/")
            if part:
                segments.append(self._safe_segment(part))
        segments.append(self._safe_segment(title))
        return "/" + "/".join(segments)

    def create_doc(self, category: str, title: str, markdown: str) -> tuple[str, str]:
        """创建文档，返回 (doc_id, path)。"""
        if not self.notebook_id:
            raise RuntimeError("尚未配置笔记本 ID。请在 GUI 中点击「更改思源笔记配置」。")
        path = self.doc_path(category, title)
        payload = {
            "notebook": self.notebook_id,
            "path": path,
            "markdown": markdown,
        }
        data = self._post("/api/filetree/createDocWithMd", payload, timeout=max(self.timeout, 30))
        return str(data.get("data") or ""), path

    def upload_assets(self, items: Iterable[tuple[str, bytes]]) -> list[str]:
        """实验性：上传图片到思源 assets，返回思源资源路径列表。

        注意：不同思源版本字段名可能不同；失败时调用方会回退为原始图片 URL。
        """
        files = []
        for filename, content in items:
            mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            files.append(("file[]", (filename, content, mime)))
        if not files:
            return []
        resp = requests.post(
            f"{self.api_base}/api/asset/upload",
            data={"assetsDirPath": "/"},
            files=files,
            headers=self._headers(),
            timeout=max(self.timeout, 30),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") not in (0, None):
            raise RuntimeError(f"上传图片失败：{data.get('msg')}")
        raw = data.get("data") or []
        paths: list[str] = []
        for item in raw:
            if isinstance(item, str):
                paths.append(item)
            elif isinstance(item, dict):
                p = item.get("dest") or item.get("path") or item.get("url")
                if p:
                    paths.append(str(p))
        return paths


if __name__ == "__main__":
    import sys
    api = sys.argv[1] if len(sys.argv) > 1 else config.SIYUAN_API_BASE
    nb_id = sys.argv[2] if len(sys.argv) > 2 else ""
    ok, msg = SiYuanClient(api, nb_id).test_connection()
    print(("OK " if ok else "FAIL ") + msg)
