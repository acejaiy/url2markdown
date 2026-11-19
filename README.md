# url2markdown

粘贴文章链接，自动抓取正文与图片，按分类保存为 **Markdown / TXT / Word(docx)** 文件。

带图形界面的桌面小工具，双击即用，无需安装 Python。针对政策新闻、微信公众号等文字文章优化：自动识别 GBK/UTF-8 编码、智能合并段落避免错行、提取正文图片、按关键词自动分类存放。

## 功能特性

- 三种导出格式：**Markdown**（图片相对路径引用）、**TXT**（纯文本 + 图片路径）、**Word / docx**（图片直接内嵌）
- 正文图片自动下载到 `assets/` 文件夹（支持微信 `data-src` 防盗链）
- 自动识别网页标题层级，还原一、二级标题结构
- 智能段落合并：加粗 / 链接 / span 等行内标签不会把一句话拆成多行
- 自动过滤资产引用、孤立括号、点赞分享等噪音
- 按关键词归类到 政治 / 经济 / 科技 / 社会 / 法治 / 国际 / 其他 子文件夹
- 支持一次粘贴多个链接批量抓取，后台线程处理不卡顿
- 保存目录可自选，默认系统桌面

## 快速开始

### 方式 A：下载 exe（推荐）

从 Releases 下载 `网页转Markdown.exe`，双击打开即可使用，无需 Python 环境。

### 方式 B：源码运行

需要 Python 3.10+（官方 CPython，自带 tkinter）：

```bash
git clone https://github.com/acejaiy/url2markdown.git
cd url2markdown
pip install -r requirements.txt
python gui.py
```

> 注意：部分精简版 Python 不带 tkinter，无法运行 GUI，请使用官方发行版。

## 使用步骤

1. 把文章链接粘贴到文本框（多个链接每行一个）
2. 选择保存位置（默认系统桌面）
3. 选择保存格式、分类方式，按需勾选图片下载
4. 点击「开始抓取并保存」，日志区实时显示进度
5. 完成后点击「打开保存文件夹」查看结果

输出结构示例：

```
桌面/
└── 科技/
    ├── 文章标题.md
    └── assets/
        ├── 文章标题_01.jpg
        └── 文章标题_02.jpg
```

## 导出格式对比

| 格式 | 图片处理 | 适合场景 |
| --- | --- | --- |
| Markdown | `![](assets/xxx.jpg)` 相对路径引用 | 笔记软件、静态博客、GitHub |
| TXT | `[图片：assets/xxx.jpg]` 路径标注 | 纯文本存档 |
| Word (docx) | 图片内嵌进文档，标题用 Word 标题样式 | 分享、打印、二次编辑 |

## 配置

所有可调项集中在 `config.py`：

| 配置项 | 作用 |
| --- | --- |
| `CATEGORIES` | 分类名及对应关键词，决定文章归入哪个文件夹 |
| `DEFAULT_CATEGORY` | 未命中关键词时的兜底分类（默认「其他」） |
| `INCLUDE_METADATA` | 是否在文首输出来源 / 作者 / 时间 / 原文链接 |
| `REQUEST_TIMEOUT` | 抓取超时秒数 |

## 打包 exe

Windows 下双击 `build.bat`，脚本会自动探测带 tkinter 的 Python 并调用 PyInstaller 生成 `dist/网页转Markdown.exe`。

手动执行：

```bash
pip install pyinstaller
python -m PyInstaller build.spec --noconfirm
```

## 项目结构

| 文件 | 作用 |
| --- | --- |
| `gui.py` | 图形界面入口（主程序） |
| `fetcher.py` | 抓取网页，提取正文、元信息与正文图片 |
| `classifier.py` | 基于关键词打分的自动分类 |
| `md_builder.py` | 渲染 Markdown / TXT / DOCX |
| `saver.py` | 下载图片到 assets、建分类文件夹、保存文件 |
| `config.py` | 可配置项 |
| `test/` | 真实抓取示例（三种格式 + assets 图片） |
| `main.py` / `exe_main.py` / `siyuan.py` | 早期命令行 / 思源版遗留，GUI 版不使用 |

## 许可证

MIT
