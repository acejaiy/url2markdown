# -*- coding: utf-8 -*-
"""网页链接转文件 —— 图形界面程序（GUI 版）。

功能：
- 粘贴网页链接（支持一次多个，每行一个）
- 选择保存目录（默认系统桌面）、导出格式（Markdown/TXT/DOCX）
- 自动/手动分类，按分类建子文件夹，正文图片下载到 assets
- 后台抓取，实时日志，完成后可打开所在文件夹
"""
from __future__ import annotations

import os
import queue
import re
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import config
from fetcher import fetch_article
from classifier import classify
from saver import save_article, FORMAT_EXT

URL_RE = re.compile(r"https?://[^\s<>\"'）)】]+", re.I)

# 统一字体配置（调大一号，改善可读性）
FONT_UI = ("Microsoft YaHei", 11)
FONT_UI_BOLD = ("Microsoft YaHei", 12, "bold")
FONT_TITLE = ("Microsoft YaHei", 18, "bold")
FONT_INPUT = ("Microsoft YaHei", 11)
FONT_LOG = ("Consolas", 11)


def default_download_dir() -> str:
    desktop = Path(os.path.expanduser("~")) / "Desktop"
    if desktop.exists():
        return str(desktop)
    cn = Path(os.path.expanduser("~")) / "桌面"
    if cn.exists():
        return str(cn)
    return str(Path.home())


def extract_urls(text: str) -> list[str]:
    urls = []
    for m in URL_RE.finditer(text or ""):
        u = m.group(0).rstrip(".,;:!?，。；：！？、")
        if u not in urls:
            urls.append(u)
    return urls


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("网页转文件")
        self.root.geometry("820x640")
        self.root.minsize(700, 520)

        try:
            root.option_add("*Font", FONT_UI)
        except Exception:
            pass

        self.msg_queue: queue.Queue = queue.Queue()
        self.running = False
        self.last_saved: list[Path] = []
        self._build_ui()
        self.root.after(100, self._poll_queue)

    def _build_ui(self):
        pad = {"padx": 14, "pady": 7}

        title = ttk.Label(self.root, text="网页链接 → 文件", font=FONT_TITLE)
        title.pack(anchor="w", **pad)
        sub = ttk.Label(
            self.root,
            text="粘贴文章链接，自动抓取正文与图片，按分类保存为 Markdown / TXT / Word。",
            font=FONT_UI, foreground="#555",
        )
        sub.pack(anchor="w", padx=14)

        frm_url = ttk.LabelFrame(self.root, text="文章链接（多个链接请每行一个）", padding=10)
        frm_url.pack(fill="x", **pad)
        self.txt_url = tk.Text(frm_url, height=5, wrap="word", font=FONT_INPUT)
        self.txt_url.pack(fill="x")

        frm_dir = ttk.LabelFrame(self.root, text="保存位置", padding=10)
        frm_dir.pack(fill="x", **pad)
        row = ttk.Frame(frm_dir)
        row.pack(fill="x")
        self.var_dir = tk.StringVar(value=default_download_dir())
        ent_dir = ttk.Entry(row, textvariable=self.var_dir, font=FONT_UI)
        ent_dir.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(row, text="浏览…", command=self._choose_dir, width=10).pack(side="left")

        frm_opt = ttk.Frame(self.root)
        frm_opt.pack(fill="x", **pad)
        ttk.Label(frm_opt, text="保存格式：", font=FONT_UI).pack(side="left")
        self.var_fmt = tk.StringVar(value="Markdown")
        cmb_fmt = ttk.Combobox(frm_opt, textvariable=self.var_fmt,
                               values=list(FORMAT_EXT.keys()), state="readonly", width=16,
                               font=FONT_UI)
        cmb_fmt.pack(side="left", padx=(0, 18))
        ttk.Label(frm_opt, text="分类方式：", font=FONT_UI).pack(side="left")
        cats = ["自动识别"] + list(config.CATEGORIES.keys()) + [config.DEFAULT_CATEGORY]
        self.var_cat = tk.StringVar(value="自动识别")
        cmb_cat = ttk.Combobox(frm_opt, textvariable=self.var_cat, values=cats,
                               state="readonly", width=13, font=FONT_UI)
        cmb_cat.pack(side="left", padx=(0, 14))
        self.var_subfolder = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm_opt, text="按分类建子文件夹", variable=self.var_subfolder).pack(side="left")

        frm_opt2 = ttk.Frame(self.root)
        frm_opt2.pack(fill="x", padx=14, pady=(0, 7))
        self.var_images = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm_opt2, text="下载正文图片到 assets 文件夹", variable=self.var_images).pack(side="left")

        frm_btn = ttk.Frame(self.root)
        frm_btn.pack(fill="x", **pad)
        self.btn_run = ttk.Button(frm_btn, text="开始抓取并保存", command=self._on_run)
        self.btn_run.pack(side="left")
        self.btn_open = ttk.Button(frm_btn, text="打开保存文件夹", command=self._open_folder, state="disabled")
        self.btn_open.pack(side="left", padx=8)

        frm_log = ttk.LabelFrame(self.root, text="运行日志", padding=10)
        frm_log.pack(fill="both", expand=True, **pad)
        self.txt_log = tk.Text(frm_log, height=9, wrap="word", font=FONT_LOG)
        self.txt_log.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frm_log, command=self.txt_log.yview)
        scroll.pack(side="right", fill="y")
        self.txt_log.configure(yscrollcommand=scroll.set)

        self._log("就绪。粘贴链接后点击「开始抓取并保存」。")

    def _log(self, msg: str):
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "done":
                    self._on_done(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.var_dir.get() or default_download_dir())
        if d:
            self.var_dir.set(d)

    def _open_folder(self):
        if not self.last_saved:
            return
        folder = str(self.last_saved[-1].parent)
        try:
            os.startfile(folder)
        except Exception:
            try:
                import subprocess
                subprocess.Popen(["explorer", folder])
            except Exception as e:
                messagebox.showerror("错误", f"无法打开文件夹：{e}")

    def _on_run(self):
        raw = self.txt_url.get("1.0", "end")
        urls = extract_urls(raw)
        if not urls:
            messagebox.showwarning("提示", "没有检测到文章链接。请粘贴一个或多个 http(s) 链接。")
            return
        base_dir = self.var_dir.get().strip()
        if not base_dir:
            messagebox.showwarning("提示", "请选择保存位置。")
            return
        try:
            Path(base_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"保存位置不可写：{e}")
            return

        self.btn_run.configure(state="disabled")
        self.btn_open.configure(state="disabled")
        self.running = True
        self.last_saved = []
        args = (urls, base_dir, self.var_cat.get(), self.var_subfolder.get(),
                self.var_fmt.get(), self.var_images.get())
        threading.Thread(target=self._worker, args=args, daemon=True).start()

    def _worker(self, urls, base_dir, cat_choice, use_sub, fmt, with_images):
        total = len(urls)
        saved: list[Path] = []
        for i, url in enumerate(urls, 1):
            self.msg_queue.put(("log", f"\n[{i}/{total}] 抓取：{url}"))
            try:
                article = fetch_article(url)
            except Exception as e:
                self.msg_queue.put(("log", f"   ✗ 抓取出错：{e}"))
                continue
            if len(article.text) < 60:
                self.msg_queue.put(("log", "   ✗ 正文内容过短，可能抓取异常，已跳过。"))
                continue
            category = cat_choice if cat_choice != "自动识别" else classify(article)
            try:
                path = save_article(article, category, base_dir, fmt, use_sub, with_images)
            except Exception as e:
                self.msg_queue.put(("log", f"   ✗ 保存失败：{e}"))
                continue
            saved.append(path)
            self.msg_queue.put(("log",
                f"   ✓ 标题：{article.title}\n"
                f"     分类：{category} | 正文 {len(article.text)} 字 | 图片 {len(article.images)} 张\n"
                f"     已保存：{path}"))
        self.msg_queue.put(("done", saved))

    def _on_done(self, saved):
        self.running = False
        self.btn_run.configure(state="normal")
        self.last_saved = saved
        if saved:
            self.btn_open.configure(state="normal")
            self._log(f"\n全部完成，成功保存 {len(saved)} 篇。")
            messagebox.showinfo("完成", f"成功保存 {len(saved)} 篇文件。")
        else:
            self._log("\n未成功保存任何文件，请检查链接或网络连接。")
            messagebox.showwarning("完成", "未成功保存任何文件。")


def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    if "--selftest" in sys.argv:
        app = App(root)
        root.update()
        result = f"TITLE={root.title()}\nWIDGETS={len(root.winfo_children())}\nOK"
        try:
            with open("selftest_result.txt", "w", encoding="utf-8") as f:
                f.write(result)
        except Exception:
            pass
        root.destroy()
        return

    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
