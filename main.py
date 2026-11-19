# -*- coding: utf-8 -*-
"""网页链接 -> Markdown -> 思源笔记  一键归档工具。

使用方式：
    python main.py <URL>               # 直接处理一个链接
    python main.py                     # 读取当前剪贴板里的链接
    python main.py --clipboard         # 同上，显式指定
    python main.py --watch             # 常驻监听剪贴板：复制新链接即自动归档
    python main.py <URL> --dry-run     # 只抓取并打印 Markdown，不写入思源
    python main.py <URL> -c 经济       # 手动指定分类（跳过自动分类）
"""
from __future__ import annotations

import argparse
import re
import sys
import time

# 修复 Windows 控制台中文乱码
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pyperclip

import config
from fetcher import fetch_article, Article
from classifier import classify
from md_builder import build_markdown
from siyuan import SiYuanClient

URL_RE = re.compile(r"https?://[^\s<>\"'）)】]+", re.I)


def find_url(text: str) -> str | None:
    """从一段文本中提取第一个 URL。"""
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(".,;:!?，。；：！？、") if m else None


def process(url: str, category_override: str | None = None,
            dry_run: bool = False, client: SiYuanClient | None = None) -> bool:
    """处理单个链接：抓取 -> 分类 -> 生成 Markdown -> 写入思源。"""
    print(f"\n{'='*60}\n[抓取] {url}")
    try:
        article: Article = fetch_article(url)
    except Exception as exc:
        print(f"[失败] 抓取出错：{exc}")
        return False

    print(f"[完成] 标题：{article.title}")
    print(f"       来源：{article.source or article.site_name} | 时间：{article.date or '未知'} "
          f"| 正文 {len(article.text)} 字")

    if len(article.text) < 60:
        print("[失败] 正文内容过短，可能抓取异常，已跳过写入。")
        return False

    category = category_override or classify(article)
    md = build_markdown(article, category)

    if dry_run:
        print(f"\n[预览模式] 分类={category}  （未写入思源）\n{'-'*60}")
        print(md)
        return True

    client = client or SiYuanClient()
    path = client.doc_path(category, article.title)
    try:
        doc_id = client.create_doc(path, md)
        print(f"[成功] 已写入思源 -> 笔记本“{config.SIYUAN_NOTEBOOK}” {path}  (id={doc_id})")
        return True
    except Exception as exc:
        print(f"[失败] 写入思源出错：{exc}")
        return False


def watch(clipboard_category: str | None, dry_run: bool) -> None:
    """常驻监听剪贴板，发现新链接即处理（相同链接不重复处理）。"""
    print(f"[监听中] 复制任意网页链接即可自动归档；间隔 {config.WATCH_INTERVAL}s。按 Ctrl+C 退出。")
    client = SiYuanClient() if not dry_run else None
    last_seen: str | None = None
    try:
        while True:
            try:
                text = pyperclip.paste()
            except Exception:
                text = ""
            url = find_url(text)
            if url and url != last_seen:
                last_seen = url
                process(url, clipboard_category, dry_run, client)
            time.sleep(config.WATCH_INTERVAL)
    except KeyboardInterrupt:
        print("\n[退出] 已停止监听。")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="抓取网页文章并归档为 Markdown 到思源笔记“笔记”笔记本。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", nargs="?", help="要抓取的网页链接（可选）")
    parser.add_argument("--clipboard", action="store_true", help="从剪贴板读取链接")
    parser.add_argument("--watch", action="store_true", help="常驻监听剪贴板，复制即归档")
    parser.add_argument("--dry-run", action="store_true", help="只预览 Markdown，不写入思源")
    parser.add_argument("-c", "--category", help="手动指定分类文件夹，跳过自动分类")
    args = parser.parse_args()

    if args.watch:
        watch(args.category, args.dry_run)
        return

    url = args.url
    if not url and (args.clipboard or True):
        # 未传 URL 时默认读剪贴板
        url = find_url(pyperclip.paste())
        if not url:
            print("[提示] 剪贴板中没有找到网页链接。请复制链接后再运行，或直接传入 URL。")
            parser.print_help()
            sys.exit(1)

    url = find_url(url) or url
    ok = process(url, args.category, args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
