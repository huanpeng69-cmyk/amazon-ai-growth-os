"""Product Agent —— 工具接口。

score_opportunity：对单个利基做多维度机会评分（相对同类目候选池归一化）。
数据来自统一数据层（amazon + keyword + review Connector），不再使用合成信号。
"""
from __future__ import annotations

from app.database import SessionLocal
from app.data import dal


def _minmax(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [50.0 for _ in values]
    return [round((v - lo) / (hi - lo) * 100, 1) for v in values]


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _to_signals(country: str, niche_keyword: str) -> list[dict]:
    """把真实市场信号转成评分逻辑所需的字段形态（无随机）。"""
    db = SessionLocal()
    try:
        signals = dal.get_market(db, country=country, category=niche_keyword)
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


def score_opportunity(niche_keyword: str, country: str = "US", budget_usd: int = 5000) -> dict:
    candidates = _to_signals(country, niche_keyword)
    if not candidates:
        return {
            "product_name": niche_keyword, "niche_keyword": niche_keyword,
            "market_size_monthly_usd": 0, "growth_yoy": 0.0,
            "competition_level": "Medium", "demand_score": 0, "competition_score": 0,
            "pain_severity_score": 0, "budget_fit_score": 0, "opportunity_score": 0,
            "top_pain": "用户未被满足的需求",
        }

    kw = niche_keyword.lower()
    match = next((c for c in candidates if kw in c["product_name"].lower() or kw in c["niche_keyword"].lower()),
                 candidates[0])

    for c in candidates:
        c["demand_raw"] = float(c["search_volume_monthly"])
        c["competition_raw"] = c["num_sellers"] * (1 + c["avg_reviews"] / 1000.0) * (1 + c["top_seller_share"] * 2)
        total = sum(p["evidence"] for p in c["pain_points"]) or 1
        c["pain_raw"] = sum(p["base_severity"] * p["evidence"] for p in c["pain_points"]) / total
        c["size"] = int(c["search_volume_monthly"] * 0.012 * c["avg_price_usd"])

    demand_norm = _minmax([c["demand_raw"] for c in candidates])
    comp_norm = [100 - v for v in _minmax([c["competition_raw"] for c in candidates])]
    idx = candidates.index(match)
    entry_cost = match["avg_price_usd"] * 150 + 1500
    budget_fit = round(_clamp(100 * budget_usd / entry_cost), 1)
    opportunity = (0.35 * demand_norm[idx] + 0.30 * comp_norm[idx]
                   + 0.20 * match["pain_raw"] + 0.15 * budget_fit)

    return {
        "product_name": match["product_name"],
        "niche_keyword": match["niche_keyword"],
        "market_size_monthly_usd": match["size"],
        "growth_yoy": match["growth_yoy"],
        "competition_level": "Low" if comp_norm[idx] >= 66 else ("Medium" if comp_norm[idx] >= 40 else "High"),
        "demand_score": demand_norm[idx],
        "competition_score": comp_norm[idx],
        "pain_severity_score": round(match["pain_raw"], 1),
        "budget_fit_score": budget_fit,
        "opportunity_score": round(opportunity, 1),
        "top_pain": match["pain_points"][0]["pain"] if match["pain_points"] else "用户未被满足的需求",
    }


PRODUCT_TOOLS = [
    {
        "name": "score_opportunity",
        "description": "对单个利基做需求/竞争/痛点/预算四维机会评分，返回可解释子分（数据来自 Connector）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "niche_keyword": {"type": "string", "description": "利基/产品关键词"},
                "country": {"type": "string", "description": "站点国家代码", "default": "US"},
                "budget_usd": {"type": "integer", "description": "入市预算（美元）", "default": 5000},
            },
            "required": ["niche_keyword"],
        },
        "handler": score_opportunity,
    },
]
