# -*- coding: utf-8 -*-
"""网页转文件 · 剪藏助手 —— V1.1.0 预览版 GUI。

小白流程：粘贴链接 → 勾选目标 → 点「开始」。
思源只需设置一次：点「更改思源笔记配置」→ 测试连接（自动列出笔记本）→ 下拉选中 → 保存。
高阶入口：destinations/ 适配器、config.py、settings.py、siyuan_client.py。
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
from classifier import classify
from destinations import ExportOptions, build_destinations
from fetcher import fetch_article
from saver import FORMAT_EXT
from settings import Settings, default_desktop_dir
from siyuan_client import SiYuanClient

URL_RE = re.compile(r"https?://[^\s<>\"'）)】]+", re.I)

FONT_UI = ("Microsoft YaHei", 12)
FONT_SMALL = ("Microsoft YaHei", 11)
FONT_TITLE = ("Microsoft YaHei", 20, "bold")
FONT_INPUT = ("Microsoft YaHei", 12)
FONT_LOG = ("Consolas", 11)
PAD = {"padx": 16, "pady": 7}


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for m in URL_RE.finditer(text or ""):
        u = m.group(0).rstrip(".,;:!?，。；：！？、")
        if u not in urls:
            urls.append(u)
    return urls


class SiYuanConfigDialog(tk.Toplevel):
    """一次性思源配置窗口。"""

    def __init__(self, parent: tk.Tk, settings: Settings, on_saved=None):
        super().__init__(parent)
        self.settings = settings
        self.on_saved = on_saved
        self.title("思源笔记配置（只需设置一次）")
        self.geometry("640x740")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        cfg = self.settings.get("siyuan", {}) or {}
        self.var_api = tk.StringVar(value=cfg.get("api_base", config.SIYUAN_API_BASE))
        self.var_id = tk.StringVar(value=cfg.get("notebook_id", ""))
        self.var_nb = tk.StringVar(value=cfg.get("notebook_name", ""))
        self.var_token = tk.StringVar(value=cfg.get("token", ""))
        self.var_prefix = tk.StringVar(value=cfg.get("path_prefix", config.SIYUAN_PATH_PREFIX))
        self.var_show_token = tk.BooleanVar(value=False)
        self.notebooks: list[dict] = []  # 缓存 [{id, name}]，供下拉选择
        self.nb_name_to_id: dict[str, str] = {}

        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="思源笔记配置", font=FONT_TITLE).pack(anchor="w", padx=20, pady=(18, 4))
        ttk.Label(
            self,
            text="填写一次即可，以后程序会自动记住。普通用户只需点「测试连接」，再从列表里选中笔记本。",
            font=FONT_SMALL, foreground="#555", wraplength=560, justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        box = ttk.LabelFrame(self, text="① API 地址（一般不用改）", padding=12)
        box.pack(fill="x", padx=20, pady=6)
        ttk.Entry(box, textvariable=self.var_api, font=FONT_INPUT).pack(fill="x")
        ttk.Label(
            box,
            text="默认：http://127.0.0.1:6806  ｜ 若改过端口，把 6806 换成你的端口即可。",
            font=FONT_SMALL, foreground="#666", wraplength=540, justify="left",
        ).pack(anchor="w", pady=(6, 0))

        box2 = ttk.LabelFrame(self, text="② 选择笔记本（点「① 测试连接」后自动列出）", padding=12)
        box2.pack(fill="x", padx=20, pady=6)
        ttk.Label(
            box2,
            text="连接成功后，下面会自动列出你的笔记本。直接选中名称即可，无需手动找 ID。",
            font=FONT_SMALL, foreground="#666", wraplength=540, justify="left",
        ).pack(anchor="w")
        self.cmb_nb = ttk.Combobox(
            box2, textvariable=self.var_nb, values=[], state="readonly", font=FONT_INPUT
        )
        self.cmb_nb.pack(fill="x", pady=(6, 4))
        self.cmb_nb.bind("<<ComboboxSelected>>", self._on_nb_selected)
        ttk.Label(
            box2,
            text="高阶：若列表未出现，可勾选「手动填 ID」自行粘贴笔记本 ID。",
            font=FONT_SMALL, foreground="#888", wraplength=540, justify="left",
        ).pack(anchor="w")
        self.var_manual = tk.BooleanVar(value=False)
        row_id = ttk.Frame(box2)
        row_id.pack(fill="x", pady=(4, 0))
        ttk.Checkbutton(
            row_id, text="手动填 ID", variable=self.var_manual,
            command=self._toggle_manual_id,
        ).pack(side="left")
        self.ent_id = ttk.Entry(row_id, textvariable=self.var_id, font=FONT_INPUT)
        self.ent_id.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self._toggle_manual_id()

        box3 = ttk.LabelFrame(self, text="③ 保存位置与高级选项", padding=12)
        box3.pack(fill="x", padx=20, pady=6)
        ttk.Label(box3, text="文档路径前缀（文章会存到：前缀 / 分类 / 标题）", font=FONT_SMALL).pack(anchor="w")
        ttk.Entry(box3, textvariable=self.var_prefix, font=FONT_INPUT).pack(fill="x", pady=(4, 10))
        row = ttk.Frame(box3)
        row.pack(fill="x")
        ttk.Label(row, text="API Token（本机使用一般留空）：", font=FONT_SMALL).pack(side="left")
        self.ent_token = ttk.Entry(row, textvariable=self.var_token, font=FONT_INPUT, show="*")
        self.ent_token.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Checkbutton(
            row, text="显示", variable=self.var_show_token, command=self._toggle_token
        ).pack(side="left")

        # ④ 连接确认栏：让用户明确看到是否配置成功
        box4 = ttk.LabelFrame(self, text="④ 连接确认（点「测试连接」后查看结果）", padding=10)
        box4.pack(fill="x", padx=20, pady=(12, 0))
        self.lbl_status = ttk.Label(
            box4,
            text="尚未验证。请先点下方「① 测试连接」，成功后从列表选中笔记本，再点「② 确认并保存」。",
            font=FONT_SMALL, foreground="#8a6d00", wraplength=560, justify="left",
        )
        self.lbl_status.pack(anchor="w")

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=20, pady=(16, 20))
        ttk.Button(btns, text="① 测试连接", command=self._test, width=14).pack(side="left")
        ttk.Button(btns, text="③ 取消", command=self.destroy, width=10).pack(side="right")
        ttk.Button(btns, text="② 确认并保存", command=self._save, width=14).pack(side="right", padx=(0, 8))

        # 按内容自适应高度，避免按钮区被挤出窗口之外
        self.update_idletasks()
        need_h = self.winfo_reqheight() + 24
        if need_h > self.winfo_height():
            self.geometry(f"640x{need_h}")

    def _toggle_token(self) -> None:
        self.ent_token.configure(show="" if self.var_show_token.get() else "*")

    def _toggle_manual_id(self) -> None:
        # 手动填 ID 时才允许编辑 ID 输入框；否则由下拉选择控制（只读）。
        self.ent_id.configure(state="normal" if self.var_manual.get() else "disabled")

    def _on_nb_selected(self, _event=None) -> None:
        name = self.var_nb.get().strip()
        nb_id = self.nb_name_to_id.get(name, "")
        if nb_id:
            self.var_id.set(nb_id)
            self.lbl_status.configure(
                text=f"✓ 已选中笔记本「{name}」（ID：{nb_id}），点「② 确认并保存」即可。",
                foreground="#1a7f37",
            )

    def _client(self) -> SiYuanClient:
        return SiYuanClient(
            api_base=self.var_api.get(),
            notebook_id=self.var_id.get(),
            token=self.var_token.get(),
            path_prefix=self.var_prefix.get(),
        )

    def _test(self) -> None:
        client = self._client()
        ok, msg = client.test_connection()
        if ok:
            self.lbl_status.configure(text="✓ " + msg.replace("\n", " "), foreground="#1a7f37")
        else:
            self.lbl_status.configure(text="✗ " + msg.replace("\n", " "), foreground="#c62828")
        # 自动拉取笔记本列表，供下拉选择（即使未填 ID 也可列出）
        try:
            self.notebooks = client.list_notebooks()
            self.nb_name_to_id = {
                str(nb.get("name") or "未命名"): str(nb.get("id") or "")
                for nb in self.notebooks if nb.get("id")
            }
            names = list(self.nb_name_to_id.keys())
            self.cmb_nb.configure(values=names)
            cur_id = self.var_id.get().strip()
            # 优先选中已保存 ID 对应的名称，否则选第一个
            match = next((n for n, i in self.nb_name_to_id.items() if i == cur_id), "")
            if match:
                self.var_nb.set(match)
                self._on_nb_selected()
            elif names and (not self.var_manual.get()):
                self.var_nb.set(names[0])
                self._on_nb_selected()
            if names:
                self.lbl_status.configure(
                    text=self.lbl_status.cget("text") + f"\n已列出 {len(names)} 个笔记本，请在「②」中选中目标。",
                    foreground="#1a7f37" if ok else "#8a6d00",
                )
        except Exception as exc:
            self.lbl_status.configure(
                text=self.lbl_status.cget("text") + f"\n（笔记本列表获取失败：{exc}）",
                foreground="#c62828",
            )
        (messagebox.showinfo if ok else messagebox.showwarning)("测试结果", msg)

    def _save(self) -> None:
        api = self.var_api.get().strip()
        nb_id = self.var_id.get().strip()
        token = self.var_token.get().strip()
        prefix = self.var_prefix.get().strip()
        if not api:
            messagebox.showwarning("提示", "请填写 API 地址（默认 http://127.0.0.1:6806）。")
            return
        if not nb_id:
            messagebox.showwarning("提示", "请先点「① 测试连接」，并从列表选中一个笔记本；或勾选「手动填 ID」自行粘贴。")
            return
        client = SiYuanClient(api_base=api, notebook_id=nb_id, token=token, path_prefix=prefix)
        ok, msg = client.test_connection()
        if ok:
            self.lbl_status.configure(text="✓ " + msg.replace("\n", " "), foreground="#1a7f37")
            nb_name = client.notebook_name() or self.var_nb.get().strip() or nb_id
        else:
            self.lbl_status.configure(text="✗ " + msg.replace("\n", " "), foreground="#c62828")
            if not messagebox.askyesno(
                "连接未通过",
                msg + "\n\n配置仍会保存，稍后可在「更改思源笔记配置」中修正。\n是否继续保存？",
            ):
                return
            nb_name = self.var_nb.get().strip() or nb_id
        self.settings.set("siyuan", {
            "api_base": api,
            "notebook_id": nb_id,
            "notebook_name": nb_name,
            "token": token,
            "path_prefix": prefix,
            "timeout": config.SIYUAN_TIMEOUT,
        })
        self.settings.set("destinations.siyuan", True)
        self.settings.save()
        if self.on_saved:
            self.on_saved()
        root = self.master
        self.destroy()
        self._show_success(root, nb_name, prefix)

    @staticmethod
    def _show_success(root: tk.Tk, notebook_name: str, prefix: str) -> None:
        """保存后弹出的「配置成功」确认界面。"""
        win = tk.Toplevel(root)
        win.title("配置成功")
        win.geometry("480x330")
        win.resizable(False, False)
        win.transient(root)
        win.grab_set()
        ttk.Label(win, text="✓ 配置成功！", font=FONT_TITLE, foreground="#1a7f37").pack(
            anchor="w", padx=24, pady=(24, 8)
        )
        ttk.Label(
            win,
            text="思源笔记已配置完成，以后无需重复设置。\n勾选「剪藏至思源笔记」即可自动写入。",
            font=FONT_UI, wraplength=430, justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 14))
        summary = ttk.LabelFrame(win, text="当前配置", padding=12)
        summary.pack(fill="x", padx=24)
        ttk.Label(summary, text=f"目标笔记本：{notebook_name}", font=FONT_SMALL).pack(anchor="w")
        clean_prefix = prefix.strip("/") or "网页剪藏"
        ttk.Label(summary, text=f"保存路径：/{clean_prefix}/分类/标题", font=FONT_SMALL).pack(
            anchor="w", pady=(4, 0)
        )
        ttk.Label(
            win,
            text="提示：路径前缀等可在「更改思源笔记配置」中随时修改。",
            font=FONT_SMALL, foreground="#666", wraplength=430, justify="left",
        ).pack(anchor="w", padx=24, pady=(12, 0))
        ttk.Button(win, text="完成", command=win.destroy, width=16).pack(pady=(18, 20))


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{config.APP_NAME}  {config.APP_VERSION}")
        self.root.geometry("940x760")
        self.root.minsize(800, 640)

        try:
            root.option_add("*Font", FONT_UI)
        except Exception:
            pass

        self.settings = Settings()
        self.dests = build_destinations(self.settings)
        self.msg_queue: queue.Queue = queue.Queue()
        self.running = False
        self.last_local_paths: list[Path] = []
        self.target_vars: dict[str, tk.BooleanVar] = {}

        self._build_ui()
        self._toggle_local_options()
        self._refresh_siyuan_status()
        self.root.after(100, self._poll_queue)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        head = ttk.Frame(self.root)
        head.pack(fill="x", padx=16, pady=(16, 2))
        ttk.Label(head, text=config.APP_NAME, font=FONT_TITLE).pack(anchor="w")
        ttk.Label(
            head,
            text="三步完成：① 粘贴链接　② 选择导出目标　③ 点「开始」",
            font=FONT_UI, foreground="#444",
        ).pack(anchor="w", pady=(4, 0))

        # ① 链接
        f1 = ttk.LabelFrame(self.root, text="① 文章链接（多个链接请每行一个）", padding=12)
        f1.pack(fill="x", **PAD)
        self.txt_url = tk.Text(f1, height=4, wrap="word", font=FONT_INPUT)
        self.txt_url.pack(fill="x")
        self.txt_url.bind("<Control-Return>", lambda _e: self.txt_url.insert("insert", "\n"))
        ttk.Label(
            f1,
            text="换行提示：按 Enter 换行；也可按 Ctrl + Enter 换行。多个链接请逐行粘贴。",
            font=FONT_SMALL, foreground="#777",
        ).pack(anchor="w", pady=(4, 0))

        # ② 目标
        f2 = ttk.LabelFrame(self.root, text="② 导出到（可多选，至少选一个）", padding=12)
        f2.pack(fill="x", **PAD)

        for key, dest in self.dests.items():
            if not dest.available:
                ttk.Label(
                    f2, text=f"○ {dest.label} —— {dest.hint}",
                    font=FONT_SMALL, foreground="#888",
                ).pack(anchor="w", pady=2)
                continue
            var = tk.BooleanVar(value=bool(self.settings.get(f"destinations.{key}", False)))
            self.target_vars[key] = var
            row = ttk.Frame(f2)
            row.pack(fill="x", pady=3)
            ttk.Checkbutton(
                row, text=dest.label, variable=var,
                command=lambda k=key: self._on_target_toggle(k),
            ).pack(side="left")
            ttk.Label(row, text=dest.hint, font=FONT_SMALL, foreground="#777").pack(side="left", padx=(12, 0))

            if key == "siyuan":
                self.lbl_siyuan = ttk.Label(f2, text="", font=FONT_SMALL, foreground="#555")
                self.lbl_siyuan.pack(anchor="w", padx=(26, 0), pady=(0, 2))
                ttk.Button(
                    f2, text="更改思源笔记配置", command=self._open_config, width=22
                ).pack(anchor="w", padx=(26, 0), pady=(0, 6))

        # 本地选项（可折叠）
        self.local_box = ttk.LabelFrame(f2, text="本地文件选项", padding=10)
        self.local_box.pack(fill="x", pady=(8, 2))

        row_dir = ttk.Frame(self.local_box)
        row_dir.pack(fill="x")
        ttk.Label(row_dir, text="保存位置：", font=FONT_SMALL).pack(side="left")
        self.var_dir = tk.StringVar(value=self.settings.get("local.dir", "") or default_desktop_dir())
        ttk.Entry(row_dir, textvariable=self.var_dir, font=FONT_INPUT).pack(
            side="left", fill="x", expand=True, padx=(4, 6)
        )
        ttk.Button(row_dir, text="浏览…", command=self._choose_dir, width=10).pack(side="left")

        row_opt = ttk.Frame(self.local_box)
        row_opt.pack(fill="x", pady=(8, 0))
        ttk.Label(row_opt, text="格式：", font=FONT_SMALL).pack(side="left")
        self.var_fmt = tk.StringVar(value=self.settings.get("local.format", config.DEFAULT_FORMAT))
        ttk.Combobox(
            row_opt, textvariable=self.var_fmt, values=list(FORMAT_EXT.keys()),
            state="readonly", width=16, font=FONT_INPUT,
        ).pack(side="left", padx=(0, 18))
        ttk.Label(row_opt, text="分类：", font=FONT_SMALL).pack(side="left")
        cats = ["自动识别"] + list(config.CATEGORIES.keys()) + [config.DEFAULT_CATEGORY]
        self.var_cat = tk.StringVar(value="自动识别")
        ttk.Combobox(
            row_opt, textvariable=self.var_cat, values=cats,
            state="readonly", width=13, font=FONT_INPUT,
        ).pack(side="left", padx=(0, 16))
        self.var_sub = tk.BooleanVar(value=bool(self.settings.get("local.use_category_folder", True)))
        ttk.Checkbutton(row_opt, text="按文章分类建子文件夹", variable=self.var_sub).pack(side="left")
        self.var_images = tk.BooleanVar(value=bool(self.settings.get("local.with_images", True)))
        ttk.Checkbutton(row_opt, text="下载正文图片", variable=self.var_images).pack(side="left", padx=(14, 0))

        # ③ 开始
        f3 = ttk.Frame(self.root)
        f3.pack(fill="x", **PAD)
        self.btn_run = ttk.Button(f3, text="开始", command=self._on_run, width=18)
        self.btn_run.pack(side="left")
        self.btn_open = ttk.Button(
            f3, text="打开保存文件夹", command=self._open_folder, state="disabled", width=18
        )
        self.btn_open.pack(side="left", padx=10)
        ttk.Label(
            f3, text="提示：勾选思源后首次会要求配置，之后只需粘贴链接 → 点开始。",
            font=FONT_SMALL, foreground="#777",
        ).pack(side="left", padx=(10, 0))

        # 日志
        f4 = ttk.LabelFrame(self.root, text="运行日志", padding=10)
        f4.pack(fill="both", expand=True, **PAD)
        self.txt_log = tk.Text(f4, height=10, wrap="word", font=FONT_LOG)
        self.txt_log.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(f4, command=self.txt_log.yview)
        scroll.pack(side="right", fill="y")
        self.txt_log.configure(yscrollcommand=scroll.set)
        self._log("就绪。粘贴文章链接后点击「开始」。")

    # ---------- 状态与持久化 ----------
    def _log(self, msg: str) -> None:
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")

    def _poll_queue(self) -> None:
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

    def _persist_settings(self) -> None:
        self.settings.set("local.dir", self.var_dir.get().strip())
        self.settings.set("local.format", self.var_fmt.get())
        self.settings.set("local.use_category_folder", self.var_sub.get())
        self.settings.set("local.with_images", self.var_images.get())
        for key, var in self.target_vars.items():
            self.settings.set(f"destinations.{key}", var.get())
        self.settings.save()

    def _toggle_local_options(self) -> None:
        show = self.target_vars.get("local")
        if show is None or show.get():
            self.local_box.pack(fill="x", pady=(8, 2))
        else:
            self.local_box.pack_forget()

    def _refresh_siyuan_status(self) -> None:
        if not hasattr(self, "lbl_siyuan"):
            return
        cfg = self.settings.get("siyuan", {}) or {}
        ready, _ = self.dests["siyuan"].is_ready()
        if ready:
            nb_name = str(cfg.get("notebook_name", ""))
            nb_id = str(cfg.get("notebook_id", ""))
            short = nb_id[:8] + "…" if len(nb_id) > 10 else nb_id
            shown = f"{nb_name}（{short}）" if nb_name else f"ID {short}"
            self.lbl_siyuan.configure(
                text=f"已配置：{cfg.get('api_base', '')} · 笔记本 {shown}",
                foreground="#1a7f37",
            )
        else:
            self.lbl_siyuan.configure(
                text="未配置：点下方按钮设置一次（测试连接 → 选中笔记本 → 保存）",
                foreground="#b26a00",
            )

    def _on_target_toggle(self, key: str) -> None:
        if key == "local":
            self._toggle_local_options()
        if key == "siyuan" and self.target_vars["siyuan"].get():
            ready, _ = self.dests["siyuan"].is_ready()
            if not ready:
                self._open_config()
        self._persist_settings()

    def _after_config_saved(self) -> None:
        if "siyuan" in self.target_vars:
            self.target_vars["siyuan"].set(True)
        self._refresh_siyuan_status()
        self._persist_settings()
        self._log("思源笔记配置已保存，后续无需重复设置。")

    def _open_config(self) -> None:
        SiYuanConfigDialog(self.root, self.settings, on_saved=self._after_config_saved)

    def _choose_dir(self) -> None:
        d = filedialog.askdirectory(initialdir=self.var_dir.get() or default_desktop_dir())
        if d:
            self.var_dir.set(d)
            self._persist_settings()

    def _open_folder(self) -> None:
        if not self.last_local_paths:
            return
        folder = str(self.last_local_paths[-1].parent)
        try:
            os.startfile(folder)
        except Exception:
            try:
                import subprocess
                subprocess.Popen(["explorer", folder])
            except Exception as exc:
                messagebox.showerror("错误", f"无法打开文件夹：{exc}")

    # ---------- 抓取流程 ----------
    def _on_run(self) -> None:
        urls = extract_urls(self.txt_url.get("1.0", "end"))
        if not urls:
            messagebox.showwarning("提示", "没有检测到文章链接。请粘贴一个或多个 http(s) 链接。")
            return
        selected = [k for k, v in self.target_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning("提示", "请至少勾选一个导出目标。")
            return
        if "local" in selected and not self.var_dir.get().strip():
            messagebox.showwarning("提示", "请选择本地保存位置。")
            return
        if "siyuan" in selected:
            ready, msg = self.dests["siyuan"].is_ready()
            if not ready:
                messagebox.showwarning("需要设置", msg + "\n\n即将打开配置窗口。")
                self._open_config()
                return

        self._persist_settings()
        options = ExportOptions(
            local_dir=self.var_dir.get().strip(),
            fmt=self.var_fmt.get(),
            use_category_folder=self.var_sub.get(),
            with_images=self.var_images.get(),
        )
        self.running = True
        self.btn_run.configure(state="disabled")
        self.btn_open.configure(state="disabled")
        self.last_local_paths = []
        threading.Thread(
            target=self._worker,
            args=(urls, self.var_cat.get(), selected, options),
            daemon=True,
        ).start()

    def _worker(self, urls: list[str], cat_choice: str,
                selected: list[str], options: ExportOptions) -> None:
        total = len(urls)
        results: list[tuple[str, str, bool]] = []
        for i, url in enumerate(urls, 1):
            self.msg_queue.put(("log", f"\n[{i}/{total}] 抓取：{url}"))
            try:
                article = fetch_article(url)
            except Exception as exc:
                self.msg_queue.put(("log", f"   ✗ 抓取出错：{exc}"))
                results.append((url, f"抓取出错：{exc}", False))
                continue
            if len(article.text) < 60:
                self.msg_queue.put(("log", "   ✗ 正文内容过短，可能抓取异常，已跳过。"))
                results.append((url, "正文内容过短", False))
                continue
            category = cat_choice if cat_choice != "自动识别" else classify(article)
            self.msg_queue.put((
                "log",
                f"   标题：{article.title}\n"
                f"   分类：{category} ｜ 正文 {len(article.text)} 字 ｜ 图片 {len(article.images)} 张",
            ))
            for key in selected:
                try:
                    msg = self.dests[key].export(article, category, options)
                    self.msg_queue.put(("log", f"   ✓ {msg}"))
                    results.append((url, msg, True))
                except Exception as exc:
                    self.msg_queue.put(("log", f"   ✗ {self.dests[key].label}失败：{exc}"))
                    results.append((url, f"{self.dests[key].label}失败：{exc}", False))
        self.msg_queue.put(("done", results))

    def _on_done(self, results: list[tuple[str, str, bool]]) -> None:
        self.running = False
        self.btn_run.configure(state="normal")
        ok = sum(1 for _, _, success in results if success)
        fail = len(results) - ok
        for _, msg, success in results:
            if success and msg.startswith("本地文件已保存："):
                raw = msg.split("：", 1)[1].strip()
                if raw:
                    self.last_local_paths.append(Path(raw))
        if self.last_local_paths:
            self.btn_open.configure(state="normal")
        self._log(f"\n完成：成功 {ok} 项，失败 {fail} 项。")
        if ok:
            messagebox.showinfo("完成", f"处理完成！成功 {ok} 项" + (f"，失败 {fail} 项。" if fail else "。"))
        else:
            messagebox.showwarning("完成", "没有成功的项目，请查看运行日志。")


def main() -> None:
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    if "--selftest" in sys.argv:
        app = App(root)
        root.update()
        result = (
            f"TITLE={root.title()}\n"
            f"VERSION={config.APP_VERSION}\n"
            f"DESTINATIONS={','.join(app.dests.keys())}\n"
            f"WIDGETS={len(root.winfo_children())}\nOK"
        )
        try:
            Path(__file__).with_name("selftest_result.txt").write_text(result, encoding="utf-8")
        except Exception:
            pass
        root.destroy()
        return

    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
