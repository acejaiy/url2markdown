# -*- coding: utf-8 -*-
"""把 CHANGELOG.md 按分类写入思源笔记。

用法：
    python tools/write_changelog_to_siyuan.py [笔记本ID]

默认笔记本：「笔记」= 20261103134419-cv3vofn
写入路径：/url2markdown/...
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from siyuan_client import SiYuanClient

DEFAULT_NOTEBOOK_ID = "20261103134419-cv3vofn"
CHANGELOG = ROOT / "CHANGELOG.md"


def section(title: str, level: int = 3) -> str:
    """提取 Markdown 中指定标题下的内容（到下一个同级或更高级标题为止）。"""
    text = CHANGELOG.read_text(encoding="utf-8")
    marker = "#" * level + " " + title
    idx = text.find(marker)
    if idx < 0:
        return f"> 未找到章节：{title}"
    start = idx + len(marker)
    m = re.search(r"\n#{1,%d} " % level, text[start:])
    end = start + m.start() if m else len(text)
    return text[start:end].strip()


def main() -> None:
    notebook_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_NOTEBOOK_ID
    full = CHANGELOG.read_text(encoding="utf-8").strip()

    overview = "\n\n".join([
        "> 由 url2markdown V1.1.0 预览版自动整理。总览为完整更新日志，下面按主题拆分为子文档。",
        section("版本总览", 2),
        section("版本时间线", 2),
        "## 分类目录\n\n" + section("写入思源的分类结构", 2),
    ])

    docs = [
        ("/url2markdown", "", "00-更新日志总览（完整）", full),
        ("/url2markdown", "更新日志", "01-版本时间线", section("版本时间线", 2)),
        ("/url2markdown", "更新日志", "02-功能新增", "\n\n".join([
            section("1. 核心功能"),
            section("2. 抓取与解析"),
            section("3. 导出格式与图片"),
            section("4. GUI 与交互"),
            section("5. 思源笔记接口"),
        ])),
        ("/url2markdown", "更新日志", "03-问题修复", section("7. 问题修复")),
        ("/url2markdown", "更新日志", "04-架构与扩展", "\n\n".join([
            section("6. 架构与扩展"),
            section("写入思源的分类结构", 2),
        ])),
        ("/url2markdown", "更新日志", "05-文档测试与发布", section("8. 文档、测试与发布")),
        ("/url2markdown", "更新日志", "06-验证记录", section("9. 验证记录")),
        ("/url2markdown", "更新日志", "07-待确认事项", section("10. 待确认事项（尚未执行）")),
        ("/url2markdown", "", "01-目录说明", overview),
    ]

    client = SiYuanClient(
        api_base=config.SIYUAN_API_BASE,
        notebook_id=notebook_id,
        path_prefix="",
    )
    ok, msg = client.test_connection()
    if not ok:
        raise RuntimeError(msg)
    print("连接成功：" + msg)

    for prefix, category, title, content in docs:
        client.path_prefix = prefix
        doc_id, path = client.create_doc(category, title, content)
        print(f"OK  {path}  id={doc_id}")


if __name__ == "__main__":
    main()
