# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：V1.1.0 预览版 GUI（无控制台、单文件）。

依赖：requests + bs4 + tkinter(标准库) + python-docx(用于导出 Word)。
新增：settings / siyuan_client / destinations 目标适配器。
注：python-docx 依赖 lxml，故 lxml 不能排除。
"""
block_cipher = None

EXCLUDES = [
    # 不需要的重型第三方库
    "trafilatura", "dateparser", "htmldate", "courlan", "justext",
    "regex", "pytz", "tzlocal", "chardet",
    "markdown", "markdown_it", "mistune",
    "numpy", "pandas", "scipy", "matplotlib", "PIL", "sklearn",
    "PyQt5", "PySide2", "wx", "curses",
    # 思源写入相关（GUI 版只生成 md 文件，不写思源）
    "siyuan",
]

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "bs4", "bs4.builder", "bs4.builder._htmlparser",
        "requests", "charset_normalizer", "idna", "urllib3", "certifi",
        "tkinter",
        "docx", "docx.oxml", "docx.opc", "lxml", "lxml.etree", "lxml._elementpath",
        "config", "fetcher", "classifier", "md_builder", "saver",
        "settings", "siyuan_client",
        "destinations", "destinations.base", "destinations.registry",
        "destinations.local_files", "destinations.siyuan", "destinations.obsidian",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="网页转文件-剪藏助手-V1.1.0预览版",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUI 版：不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
