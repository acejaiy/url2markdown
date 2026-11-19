# -*- coding: utf-8 -*-
"""保存模块：把文章保存为 Markdown / TXT / DOCX，图片下载到 assets 文件夹。

目录结构（use_category_folder=True 时）：
    保存目录/分类/文章标题.md
    保存目录/分类/assets/文章标题_01.jpg
三种格式共用同一个 assets 文件夹，避免重复下载。
"""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from config import USER_AGENT, REQUEST_TIMEOUT
from fetcher import Article
from md_builder import build_markdown, build_txt, iter_blocks

FORMAT_EXT = {"Markdown": ".md", "TXT": ".txt", "Word (DOCX)": ".docx"}


def safe_filename(title: str, max_len: int = 80) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title or "")
    name = re.sub(r"\s+", " ", name).strip(" .")
    return (name[:max_len] or "未命名文章")


def _unique_path(target_dir: Path, stem: str, ext: str) -> Path:
    candidate = target_dir / f"{stem}{ext}"
    idx = 2
    while candidate.exists():
        candidate = target_dir / f"{stem} ({idx}){ext}"
        idx += 1
    return candidate


def _ext_from_url(url: str, content_type: str = "") -> str:
    path = urlparse(url).path.lower()
    m = re.search(r"\.(jpg|jpeg|png|gif|webp|bmp|svg)$", path)
    if m:
        ext = m.group(1)
        return ".jpg" if ext == "jpeg" else f".{ext}"
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0])
        if guessed:
            return ".jpg" if guessed in (".jpe", ".jpeg") else guessed
    return ".jpg"


def download_images(article: Article, assets_dir: Path, stem: str) -> dict[int, str]:
    """下载正文图片到 assets 文件夹，返回 {索引: 文档内相对路径}。"""
    result: dict[int, str] = {}
    if not article.images:
        return result
    assets_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": USER_AGENT, "Referer": article.url}
    for idx, url in enumerate(article.images, 1):
        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            if len(resp.content) < 100:  # 1x1 占位图等
                continue
            ext = _ext_from_url(url, resp.headers.get("Content-Type", ""))
            fname = f"{safe_filename(stem, 40)}_{idx:02d}{ext}"
            fpath = assets_dir / fname
            fpath.write_bytes(resp.content)
            result[idx - 1] = f"assets/{fname}"
        except Exception:
            # 单张失败不影响整体，Markdown 里会跳过该图
            continue
    return result


def _save_docx(article: Article, category: str, img_map: dict[int, str], out: Path) -> None:
    from docx import Document
    from docx.shared import Inches

    doc = Document()
    base = out.parent
    for kind, text in iter_blocks(article, category, img_map):
        if kind == "title":
            doc.add_heading(text, level=0)
        elif kind == "meta":
            p = doc.add_paragraph(text)
            for run in p.runs:
                run.font.size = None
        elif kind == "heading":
            level, title = text
            doc.add_heading(title, level=min(max(level - 1, 1), 6))
        elif kind == "image":
            fpath = base / text
            if fpath.exists():
                try:
                    doc.add_picture(str(fpath), width=Inches(5.5))
                except Exception:
                    doc.add_paragraph(f"[图片：{text}]")
        else:
            doc.add_paragraph(text)
    doc.save(str(out))


def save_article(article: Article, category: str, base_dir: str | Path,
                 fmt: str = "Markdown", use_category_folder: bool = True,
                 with_images: bool = True) -> Path:
    """保存文章为指定格式，返回最终文件路径。fmt ∈ FORMAT_EXT。"""
    ext = FORMAT_EXT.get(fmt, ".md")
    base = Path(base_dir)
    target_dir = base / category if use_category_folder else base
    target_dir.mkdir(parents=True, exist_ok=True)

    stem = safe_filename(article.title)
    img_map: dict[int, str] = {}
    if with_images and article.images:
        img_map = download_images(article, target_dir / "assets", stem)

    out = _unique_path(target_dir, stem, ext)
    if ext == ".md":
        out.write_text(build_markdown(article, category, img_map), encoding="utf-8")
    elif ext == ".txt":
        out.write_text(build_txt(article, category, img_map), encoding="utf-8")
    elif ext == ".docx":
        _save_docx(article, category, img_map, out)
    else:
        out.write_text(build_markdown(article, category, img_map), encoding="utf-8")
    return out


if __name__ == "__main__":
    a = Article(url="https://example.com/a", title="测试文档",
                text="正文第一段。\n[[IMG:0]]", images=[])
    p = save_article(a, "科技", ".", "TXT")
    print("已保存:", p)
