"""VOC Agent —— 工具接口。

fetch_reviews：经统一数据层获取真实评论痛点（review_connector），不再使用合成信号。
"""
from __future__ import annotations

from app.database import SessionLocal
from app.data import dal


def fetch_reviews(product_name: str, country: str = "US") -> dict:
    db = SessionLocal()
    try:
        products = dal.list_products(db, keyword=product_name, country=country)
    finally:
        db.close()
    asin = products[0].asin if products else None

    reviews = []
    if asin:
        db2 = SessionLocal()
        try:
            reviews = dal.get_reviews(db2, asin=asin, country=country)
        finally:
            db2.close()

    counter: dict[str, int] = {}
    for r in reviews:
        for pk in r.pain_keywords:
            counter[pk] = counter.get(pk, 0) + 1

    pain_points = [
        {"pain": k, "base_severity": min(100, 45 + v * 5), "evidence": v}
        for k, v in sorted(counter.items(), key=lambda x: -x[1])
    ]
    return {
        "product_name": product_name,
        "growth_yoy": None,
        "pain_points": pain_points,
        "review_count": len(reviews),
    }


VOC_TOOLS = [
    {
        "name": "fetch_reviews",
        "description": "抓取指定产品的真实评论痛点（含严重度与证据量），数据来自 review_connector。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "产品/利基名称"},
                "country": {"type": "string", "description": "站点国家代码", "default": "US"},
            },
            "required": ["product_name"],
        },
        "handler": fetch_reviews,
    },
]
