# -*- coding: utf-8 -*-
"""抓取模块：输入网页 URL，提取正文、标题、发布时间、来源、正文图片。

针对政策 / 新闻 / 公众号等文字文章优化，依赖极简（requests + bs4 + lxml）。
关键点：
1. 用 BeautifulSoup 按「块级元素」拼段落，行内标签（strong/span/a/em 等）
   的文字直接拼接，不再各自换行 —— 修复段落被拆成多行的错行问题；
2. 正文中的 <img> 按出现顺序提取，在文本里留 [[IMG:index]] 占位，
   供后续下载到 assets 并生成 Markdown 图片语法；
3. 使用 html.parser 解析，兼容畸形 HTML，同时自动识别 GBK/UTF-8 编码。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from config import REQUEST_TIMEOUT, USER_AGENT

# 常见正文容器（按优先级排列）
_CONTENT_SELECTORS = [
    "#UCAP-CONTENT", ".trs_editor_view", ".TRS_UEDITOR", ".viewTRS_Ueditor",
    ".TRS_Editor", "#Zoom", "#zoom", ".pages_content",
    "article", ".article-content", ".articleContent", ".article_content",
    ".detail-content", ".detailContent", ".news-content", ".news_content",
    ".post-content", ".entry-content", ".rich_media_content",  # 微信公众号
    ".content-article", ".artical", "#artibody", "#article", ".article",
    ".content", "#content", "main",
]

# 需要从正文中剔除的噪音行（整行匹配）
_NOISE_PATTERNS = [
    r"^\s*(责任编辑|编辑[:：]|来源[:：]|原标题[:：]|扫一扫|分享到|点击上方|版权声明)",
    r"^\s*(免责声明|本文由|转载请|版权归原作者)",
    r"@\w+#\d+\s*[:：]\s*\S+",  # 思源/剪贴板资产引用 @image#1:xxx
    r"^\s*(点赞|在看|分享|收藏|转发|扫码|关注我们|点击关注)[!！。.·\s]*$",
    r"^\s*[（()\）)\s]+$",  # 孤立的括号行
]

# 块级元素：遍历到此，把累积的行内文字作为一个段落输出，并插入段落分隔
_BLOCK_TAGS = {
    "p", "div", "li", "ul", "ol", "blockquote", "section", "article",
    "tr", "td", "th", "table", "figure", "figcaption", "header", "footer",
    "br", "hr", "pre", "h1", "h2", "h3", "h4", "h5", "h6",
}
# 行内元素：文字直接拼接，不单独换行
_SKIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "form", "button"}


@dataclass
class Article:
    url: str
    title: str = "未命名文章"
    content_html: str = ""
    text: str = ""
    author: str = ""
    date: str = ""
    source: str = ""
    site_name: str = ""
    images: list[str] = field(default_factory=list)  # 正文图片 URL（按出现顺序）
    raw_html: str = field(default="", repr=False)

    @property
    def domain(self) -> str:
        try:
            return urlparse(self.url).netloc
        except Exception:
            return ""


def _detect_encoding(resp: requests.Response) -> str:
    enc = resp.encoding
    if not enc or enc.lower() in ("iso-8859-1",):
        enc = resp.apparent_encoding or "utf-8"
    if enc and enc.lower() in ("gb2312", "gb18030"):
        enc = "gbk"
    return enc or "utf-8"


def _html_from_response(resp: requests.Response) -> str:
    enc = _detect_encoding(resp)
    try:
        return resp.content.decode(enc, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return resp.content.decode("utf-8", errors="replace")


def _clean_text(text: str) -> str:
    """清理正文：去噪音行、压缩空行（按块拼接后每行即一段）。"""
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if any(re.search(p, line) for p in _NOISE_PATTERNS):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _looks_like_nav(text: str) -> bool:
    if not text or len(text) > 300:
        return False
    nav_words = ["首页", "登录", "个人中心", "退出", "邮箱", "无障碍",
                 "简", "繁", "EN", "版权所有", "网站地图"]
    return sum(1 for w in nav_words if w in text) >= 4


def _meta_content(soup: BeautifulSoup, pairs: list[tuple[str, str]]) -> str:
    for attr, val in pairs:
        tag = soup.find("meta", attrs={attr: val})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def _img_url(img: Tag, base_url: str) -> str:
    """取图片真实地址：微信 data-src 优先，其次 src / data-original。"""
    for attr in ("data-src", "data-original", "data-lazy-src", "src"):
        u = (img.get(attr) or "").strip()
        if u and not u.startswith("data:"):
            return urljoin(base_url, u)
    return ""


def _node_to_text_and_images(node, base_url: str) -> tuple[str, list[str]]:
    """把 DOM 节点转成「按块分段的正文」+「按出现顺序的图片 URL 列表」。

    - 行内标签的文字直接拼到当前段落，不再各自换行（修复错行）
    - h1~h6 标记为 [[Hn]]...[[/Hn]]，供 md_builder 还原标题层级
    - img 在正文里留 [[IMG:index]] 占位
    """
    out: list[str] = []
    images: list[str] = []
    buf: list[str] = []          # 当前段落累积的文字
    heading_level: int | None = None

    def flush() -> None:
        nonlocal heading_level
        text = "".join(buf)
        text = re.sub(r"\s+", " ", text).strip()
        buf.clear()
        if not text:
            heading_level = None
            return
        # 正文里的图片占位也是一块，独立成行
        if heading_level is not None:
            out.append(f"\n[[H{heading_level}]]{text}[[/H{heading_level}]]\n")
            heading_level = None
        else:
            out.append(text + "\n")

    def walk(el) -> None:
        if isinstance(el, NavigableString):
            s = str(el)
            if s.strip():
                buf.append(s.strip())
            return
        if not isinstance(el, Tag):
            return
        name = el.name.lower()
        if name in _SKIP_TAGS:
            return
        # 标题：不管内部有多少行内标签，整体作为一个标题块
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            flush()
            title_text = re.sub(r"\s+", " ", el.get_text("", strip=True)).strip()
            if title_text:
                out.append(f"\n[[H{name[1]}]]{title_text}[[/H{name[1]}]]\n")
            return
        # 图片：作为一个独立块
        if name == "img":
            flush()
            u = _img_url(el, base_url)
            if u:
                images.append(u)
                out.append(f"[[IMG:{len(images) - 1}]]\n")
            return
        # 递归子节点
        for child in el.children:
            walk(child)
        # 块级元素结束 -> 结束当前段落
        if name in _BLOCK_TAGS:
            flush()

    walk(node)
    flush()
    return "".join(out), images


def _extract_with_soup(html: str, url: str) -> tuple[str, dict, list[str]]:
    """用 BeautifulSoup 提取正文、元信息与图片（html.parser，无需 lxml）。"""
    soup = BeautifulSoup(html, "html.parser")
    meta: dict = {}

    title = _meta_content(soup, [("property", "og:title"), ("name", "twitter:title")])
    if not title and soup.title:
        title = soup.title.get_text(strip=True)
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
    meta["title"] = title

    date = _meta_content(soup, [
        ("property", "article:published_time"), ("name", "publishdate"),
        ("name", "PubDate"), ("name", "weibo: article:create_at"),
        ("name", "date"), ("name", "firstpublishedtime"),
    ])
    if not date:
        m = re.search(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})", html[:8000])
        if m:
            date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    meta["date"] = date

    author = _meta_content(soup, [("name", "author"), ("property", "article:author")])
    meta["author"] = author

    source = _meta_content(soup, [
        ("name", "source"), ("name", "Source"),
        ("property", "og:site_name"), ("name", "site_name"),
    ])
    meta["source"] = source
    meta["site_name"] = _meta_content(soup, [("property", "og:site_name"), ("name", "site_name")])

    # 正文容器：候选中取文字量最大的节点
    best = None
    best_len = 0
    for sel in _CONTENT_SELECTORS:
        for node in soup.select(sel):
            length = len(node.get_text(strip=True))
            if length > best_len:
                best, best_len = node, length
    node = best if best is not None else (soup.body or soup)
    body_text, images = _node_to_text_and_images(node, url)
    return _clean_text(body_text), meta, images


def _clean_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "")).strip()
    t = re.split(r"[_|—–]\s*[^_|—–]{0,10}(政府网|新闻网|网|日报|晚报|时报|在线|中国网|央广网)", t)[0]
    t = re.split(r"\s+-\s+[^-\s]{2,12}$", t)[0]
    t = re.sub(r"_(其他|政策|解读|通知|公告|要闻|头条|正文|最新)$", "", t)
    return t.strip(" _|-—–") or "未命名文章"


def fetch_article(url: str) -> Article:
    """抓取并提取文章。失败时抛异常，由调用方处理。"""
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url

    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"}
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    html = _html_from_response(resp)
    final_url = resp.url or url

    article = Article(url=final_url, raw_html=html)
    article.site_name = urlparse(final_url).netloc

    soup_text, soup_meta, images = _extract_with_soup(html, final_url)
    for key in ("title", "date", "author", "source", "site_name"):
        if soup_meta.get(key):
            setattr(article, key, soup_meta[key])
    article.images = images

    if not soup_text or _looks_like_nav(soup_text):
        _soup = BeautifulSoup(html, "html.parser")
        fallback, fb_images = _node_to_text_and_images(_soup.body or _soup, final_url)
        fallback = _clean_text(fallback)
        if len(fallback) > len(soup_text):
            soup_text = fallback
            article.images = fb_images

    article.text = soup_text
    article.title = _clean_title(article.title)
    return article


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python fetcher.py <URL>")
        raise SystemExit(1)
    a = fetch_article(sys.argv[1])
    print("标题:", a.title)
    print("时间:", a.date, "| 来源:", a.source or a.site_name, "| 作者:", a.author)
    print("正文字数:", len(a.text), "| 图片数:", len(a.images))
    print("----正文预览----")
    print(a.text[:800])
