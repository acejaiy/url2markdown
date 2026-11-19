# -*- coding: utf-8 -*-
"""把抓取到的 Article 渲染成 Markdown / 纯文本 / DOCX。

标题层级规则：
- 文章标题 -> H1
- 网页 <h2> / 一、 -> H2；<h3> / （一） -> H3；依次顺延
正文里的 [[IMG:n]] 占位会渲染成图片（Markdown 语法 / DOCX 内嵌图片）。
"""
from __future__ import annotations

import re
from pathlib import Path

from fetcher import Article
from config import INCLUDE_METADATA

# 抓取阶段注入的标题标记
_MARK_RE = re.compile(r"\[\[H([1-6])\]\](.*?)\[\[/H\1\]\]")
_IMG_RE = re.compile(r"\[\[IMG:(\d+)\]\]")

_NUMBERED_RULES: list[tuple[re.Pattern, int]] = [
    (re.compile(r"^第[一二三四五六七八九十百]+[章节篇部]\s*\S.{0,40}$"), 2),
    (re.compile(r"^[一二三四五六七八九十]+[、.．]\s*\S.{0,60}$"), 2),
    (re.compile(r"^[（(][一二三四五六七八九十\d]+[)）]\s*\S.{0,60}$"), 3),
    (re.compile(r"^\d+[、.．]\s*\S.{0,60}$"), 3),
]


def _same_title(a: str, b: str) -> bool:
    def norm(s: str) -> str:
        return re.sub(r"[\s·｜|—\-：:]", "", (s or "")).lower()
    na, nb = norm(a), norm(b)
    return bool(na) and bool(nb) and (na == nb or na in nb or nb in na)


def _numbered_level(line: str) -> int | None:
    s = line.strip()
    if not s or len(s) > 80:
        return None
    for pattern, level in _NUMBERED_RULES:
        if pattern.match(s):
            return level
    return None


def _meta_lines(article: Article, category: str) -> list[str]:
    lines = []
    if article.source or article.site_name:
        lines.append(f"- **来源**：{article.source or article.site_name}")
    if article.author:
        lines.append(f"- **作者**：{article.author}")
    if article.date:
        lines.append(f"- **发布时间**：{article.date}")
    lines.append(f"- **原文链接**：<{article.url}>")
    lines.append(f"- **分类**：{category}")
    return lines


def _render_md_line(line: str, article_title: str, img_map: dict[int, str]) -> list[str]:
    """把一行转成若干 Markdown 行：标题标记还原 + 图片占位替换。"""
    stripped = line.strip()
    if not stripped:
        return []
    # 纯图片行
    m = _IMG_RE.fullmatch(stripped)
    if m:
        idx = int(m.group(1))
        rel = img_map.get(idx)
        return [f"![]({rel})"] if rel else []

    rendered: list[str] = []
    cursor = 0
    for m in _MARK_RE.finditer(stripped):
        before = stripped[cursor:m.start()].strip()
        if before:
            rendered.append(before)
        level = int(m.group(1))
        title_text = m.group(2).strip()
        if title_text:
            if level == 1 and _same_title(title_text, article_title):
                cursor = m.end()
                continue
            rendered.append("#" * min(level if level > 1 else 2, 6) + " " + title_text)
        cursor = m.end()
    after = stripped[cursor:].strip()
    if after:
        # 行内可能还有图片标记
        def repl(im):
            rel = img_map.get(int(im.group(1)))
            return f"![]({rel})" if rel else ""
        rendered.append(_IMG_RE.sub(repl, after))

    out: list[str] = []
    for item in rendered:
        lvl = _numbered_level(item)
        out.append("#" * lvl + " " + item if lvl else item)
    return out


def build_markdown(article: Article, category: str,
                   img_map: dict[int, str] | None = None) -> str:
    """生成 Markdown 文本。img_map: 索引 -> 图片相对路径（如 assets/xxx.jpg）。"""
    img_map = img_map or {}
    parts = [f"# {article.title}", ""]
    if INCLUDE_METADATA:
        parts.append("> " + "\n> ".join(_meta_lines(article, category)))
        parts.append("")
    for line in (article.text or "").split("\n"):
        for item in _render_md_line(line, article.title, img_map):
            parts.append(item)
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def build_txt(article: Article, category: str,
              img_map: dict[int, str] | None = None) -> str:
    """生成纯文本（去掉 Markdown 标记，保留标题文字与图片相对路径）。"""
    img_map = img_map or {}
    parts = [article.title, "=" * max(4, len(article.title)), ""]
    if INCLUDE_METADATA:
        for line in _meta_lines(article, category):
            parts.append(re.sub(r"\*\*|<|>", "", line))
        parts.append("")
    for line in (article.text or "").split("\n"):
        s = line.strip()
        if not s:
            continue
        # 标题标记 -> 纯标题文字
        m = _MARK_RE.fullmatch(s)
        if m:
            s = m.group(2).strip()
        im = _IMG_RE.fullmatch(s)
        if im:
            rel = img_map.get(int(im.group(1)))
            if rel:
                parts.append(f"[图片：{rel}]")
                parts.append("")
            continue
        parts.append(s)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def iter_blocks(article: Article, category: str, img_map: dict[int, str] | None = None):
    """产出 (kind, text) 块序列，供 DOCX 渲染：title/heading/para/image/meta。"""
    img_map = img_map or {}
    yield ("title", article.title)
    if INCLUDE_METADATA:
        yield ("meta", "  ".join(re.sub(r"\*\*|<|>", "", l) for l in _meta_lines(article, category)))
    for line in (article.text or "").split("\n"):
        s = line.strip()
        if not s:
            continue
        im = _IMG_RE.fullmatch(s)
        if im:
            rel = img_map.get(int(im.group(1)))
            if rel:
                yield ("image", rel)
            continue
        m = _MARK_RE.fullmatch(s)
        if m:
            level, title = int(m.group(1)), m.group(2).strip()
            if level == 1 and _same_title(title, article.title):
                continue  # 与文首标题重复，跳过
            yield ("heading", (level, title))
            continue
        lvl = _numbered_level(s)
        if lvl:
            yield ("heading", (lvl, s))
        else:
            yield ("para", s)


if __name__ == "__main__":
    a = Article(
        url="https://example.com/a", title="测试标题",
        text="[[H2]]一、总体要求[[/H2]]\n这是正文第一段。\n[[IMG:0]]\n[[H3]]（一）细化目标[[/H3]]\n这是正文第二段。",
        images=["https://example.com/a.jpg"], source="测试网", date="2026-01-01",
    )
    m = {"0": "assets/a.jpg", 0: "assets/a.jpg"}
    print(build_markdown(a, "政治", m))
