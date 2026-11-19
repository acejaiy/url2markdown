# -*- coding: utf-8 -*-
"""exe 交互入口：双击运行后进入交互循环，粘贴链接回车即归档。

同时保留命令行用法（供高级用户在 CMD 里调用）：
    url2siyuan.exe <URL>
    url2siyuan.exe --watch
    url2siyuan.exe --dry-run <URL>
    url2siyuan.exe -c 经济 <URL>
"""
from __future__ import annotations

import sys

# 修复 Windows 控制台/管道下的中文乱码：强制 UTF-8 输出并把控制台代码页设为 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
try:
    import ctypes
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)
except Exception:
    pass

import pyperclip

import config
from main import find_url, process, watch as watch_loop
from siyuan import SiYuanClient

BANNER = r"""
   ______   __        __        _   __       _
  /_  __/  / /  ____ _/ /_____ _/ | / /____ _(_)____
   / /    / /  / __ `/ //_/ __ `/  |/ // __ `/ / __ \
  / /    / /  / /_/ / ,< / /_/ / /|  // /_/ / / / / /
 /_/    /_/   \__,_/_/|_|\__,_/_/ |_/ \__, /_/_/ /_/
                                      /____/
        网页链接  ->  Markdown  ->  思源笔记「笔记」
"""


def interactive() -> None:
    print(BANNER)
    print(f"目标笔记本：{config.SIYUAN_NOTEBOOK}  |  分类：{', '.join(config.CATEGORIES)}、{config.DEFAULT_CATEGORY}")
    print("-" * 60)
    print("使用说明：")
    print("  · 直接粘贴网页链接 + 回车  -> 抓取并归档")
    print("  · 按回车（留空）            -> 读取剪贴板中的链接")
    print("  · 输入 watch                -> 常驻监听剪贴板（复制即归档）")
    print("  · 输入 q / quit             -> 退出")
    print("-" * 60)

    client = SiYuanClient()
    while True:
        try:
            raw = input("\n[链接]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break

        cmd = raw.lower()
        if cmd in ("q", "quit", "exit", "退出"):
            print("已退出。")
            break
        if cmd in ("watch", "监听", "w"):
            watch_loop(None, False)
            continue

        if not raw:
            try:
                raw = pyperclip.paste() or ""
            except Exception:
                raw = ""
            url = find_url(raw)
            if not url:
                print("[提示] 剪贴板里没有链接，请先把文章链接复制到剪贴板。")
                continue
        else:
            url = find_url(raw) or raw

        process(url, client=client)


def main() -> None:
    # 有参数时走原命令行逻辑（--watch / --dry-run / -c 等）
    if len(sys.argv) > 1:
        from main import main as cli_main
        cli_main()
    else:
        interactive()


if __name__ == "__main__":
    main()
