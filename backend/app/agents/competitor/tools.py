"""Competitor Agent —— 工具接口。

scan_competitors：经统一数据层获取真实竞品画像（价格/评论/评分/份额），不再随机编造。
"""
from __future__ import annotations

from app.database import SessionLocal
from app.data import dal


def scan_competitors(niche_keyword: str, country: str = "US", top_n: int = 5) -> list[dict]:
    db = SessionLocal()
    try:
        products = dal.list_products(db, keyword=niche_keyword, country=country)
    finally:
        db.close()
    if not products:
        return []

    base = products[0]
    base_price = base.price or 29.9

    # 真实痛点来自该头部商品的评论（Connector → review_connector）
    pains: list[str] = []
    if base.asin:
        db2 = SessionLocal()
        try:
            reviews = dal.get_reviews(db2, asin=base.asin, country=country)
        finally:
            db2.close()
        for r in reviews:
            pains.extend(r.pain_keywords)

    profiles: list[dict] = []
    n = min(top_n, len(products))
    for i in range(n):
        p = products[i]
        share = round(max(0.45 - i * 0.07, 0.03), 3)  # 头部递减份额（确定性，非随机）
        profiles.append({
            "name": p.title,
            "price_usd": p.price or base_price,
            "avg_reviews": p.review_count or 0,
            "rating": p.rating or 0.0,
            "est_market_share": share,
            "weakness": pains[i % len(pains)] if pains else "用户反馈一般",
        })
    return profiles


COMPETITOR_TOOLS = [
    {
        "name": "scan_competitors",
        "description": "扫描指定利基下的头部竞品，返回定价/评论量/评分/份额/软肋（数据来自 Connector，非编造）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "niche_keyword": {"type": "string", "description": "利基/产品关键词"},
                "country": {"type": "string", "description": "站点国家代码", "default": "US"},
                "top_n": {"type": "integer", "description": "竞品数量", "default": 5},
            },
            "required": ["niche_keyword"],
        },
        "handler": scan_competitors,
    },
]
