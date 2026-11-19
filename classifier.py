# -*- coding: utf-8 -*-
"""自动归类模块：根据标题 + 正文关键词给文章打分，选出最合适的分类文件夹。"""
from __future__ import annotations

from fetcher import Article
from config import CATEGORIES, DEFAULT_CATEGORY, CLASSIFY_TEXT_LIMIT


def classify(article: Article) -> str:
    """返回分类名（用作保存文件夹名）。

    打分规则：
    - 标题命中关键词权重 x3（标题信息密度最高）；
    - 正文命中关键词权重 x1；
    - 得分最高且 > 0 的分类胜出，否则返回默认分类。
    """
    title = article.title or ""
    body = (article.text or "")[:CLASSIFY_TEXT_LIMIT]
    scores: dict[str, int] = {name: 0 for name in CATEGORIES}

    for name, keywords in CATEGORIES.items():
        for kw in keywords:
            if not kw:
                continue
            if kw.lower() in title.lower():
                scores[name] += 3
            if kw.lower() in body.lower():
                scores[name] += 1

    best = max(scores, key=scores.get) if scores else DEFAULT_CATEGORY
    if scores.get(best, 0) <= 0:
        return DEFAULT_CATEGORY
    return best


if __name__ == "__main__":
    a = Article(url="x", title="国务院办公厅关于发展新质生产力的意见",
                text="要大力发展新质生产力，推动产业创新，促进经济高质量发展。")
    print("分类结果:", classify(a))
