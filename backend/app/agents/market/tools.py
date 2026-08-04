"""Market Agent —— 工具接口（Tool Interface）。

每个工具含：name / description / input_schema(JSON Schema) / handler(可调用)。
Agent 通过 handler 经统一数据层（DAL → Connector → DB）获取真实市场信号，
不再使用任何随机/合成数据。
"""
from __future__ import annotations

from app.database import SessionLocal
from app.data import dal


def search_market(country: str, category: str, pool_size: int = 24):
    """采集指定国家/类目的候选利基市场信号（真实数据，来自 amazon+keyword+review Connector）。"""
    db = SessionLocal()
    try:
        signals = dal.get_market(db, country=country, category=category)
    finally:
        db.close()

    out = []
    for s in signals:
        pains = [
            {"pain": p["pain"], "base_severity": 60, "evidence": p.get("evidence", 0)}
            for p in s.pain_points
        ]
        out.append({
            "product_name": s.product_name,
            "niche_keyword": s.niche_keyword,
            "search_volume_monthly": s.search_volume_monthly or 0,
            "avg_price_usd": s.avg_price_usd or 0.0,
            "num_sellers": s.num_sellers or 0,
            "avg_reviews": s.avg_reviews or 0,
            "top_seller_share": s.top_seller_share or 0.15,
            "growth_yoy": s.growth_yoy or 0.0,
            "pain_points": pains,
        })
    return out


MARKET_TOOLS = [
    {
        "name": "search_market",
        "description": "采集指定国家/类目下的候选利基市场信号：搜索量、价格带、竞品数、评论数、头部集中度、增速、用户痛点。",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string", "description": "站点国家代码"},
                "category": {"type": "string", "description": "Amazon 类目"},
                "pool_size": {"type": "integer", "description": "候选利基数量", "default": 24},
            },
            "required": ["country", "category"],
        },
        "handler": search_market,
    },
]
