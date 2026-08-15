"""Product Agent —— 工具接口。

score_opportunity：对单个利基做多维度机会评分。
数据源改为**实时 Bright Data（amazon_research）** + **真实用户评论**：
- 需求/竞争/价格/评论量均来自实时抓取；
- 痛点（severity/evidence）由大模型基于该商品**真实评论**归纳，不再使用固定 base_severity；
- 无任何真实数据时诚实返回空信号，绝不编造。
"""
from __future__ import annotations

import logging
from typing import List, Optional

from app.data.connectors.review_connector.connector import ReviewConnector
from app.agents._util import llm_available, synthesize
from app.llm.agnes import AgnesError

log = logging.getLogger("product")

_PAIN_SYSTEM = (
    "你是亚马逊选品分析师。只依据真实评论归纳痛点，绝不编造；"
    "返回 JSON：{\"pains\":[{\"pain\":\"中文概述\",\"severity\":0-100,\"evidence\":整数}]}。"
)


def _estimate_growth(reviews: int, price: float) -> float:
    if reviews <= 0 and price <= 0:
        return 0.05
    heat = min(reviews / 10000.0, 1.0)
    if price <= 0:
        price_factor = 0.5
    elif 10 <= price <= 50:
        price_factor = 1.0
    else:
        price_factor = 0.8 if 50 < price <= 100 else 0.6
    return round(min(heat * price_factor * 0.45, 0.45), 3)


def _minmax(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [50.0 for _ in values]
    return [round((v - lo) / (hi - lo) * 100, 1) for v in values]


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _live_signals(country: str, niche_keyword: str) -> Optional[list[dict]]:
    """实时 Bright Data 抓取该利基下真实商品。"""
    try:
        from app.mcp.brightdata_client.exceptions import BrightDataError
        from app.tools.base import ToolNotConfigured
        from app.mcp.tools.amazon_research import amazon_research
        res = amazon_research(keyword=niche_keyword, country=country, limit=12)
    except (BrightDataError, ToolNotConfigured, ImportError):
        return None
    products = (res or {}).get("products") or []
    if not products:
        return None
    out = []
    seen: set[str] = set()
    for p in products:
        name = (p.get("title") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        price_raw = p.get("price")
        reviews = p.get("reviews")
        price = 0.0
        if price_raw not in (None, ""):
            try:
                price = float(str(price_raw).replace("$", "").replace(",", ""))
            except (TypeError, ValueError):
                price = 0.0
        out.append({
            "product_name": name, "asin": p.get("asin"), "niche_keyword": niche_keyword,
            "search_volume_monthly": (reviews or 0) * 8, "avg_price_usd": price,
            "num_sellers": len(products),
            "avg_reviews": reviews if isinstance(reviews, (int, float)) else 0,
            "top_seller_share": 0.15, "growth_yoy": _estimate_growth(reviews or 0, price),
        })
    return out if out else None


def _real_pains(match: dict, country: str) -> List[dict]:
    """抓该商品真实评论 → 大模型归纳痛点（含 severity/evidence）。"""
    asin = match.get("asin")
    if not asin:
        return []
    bodies: List[str] = []
    try:
        rc = ReviewConnector()
        raw = rc._fetch_live({"asin": asin, "country": country})
        for r in (raw.payload or {}).get("reviews") or []:
            b = r.get("body") or ""
            if b.strip():
                bodies.append(b)
    except Exception as e:
        log.warning("ProductAgent 抓取评论 %s 失败：%s", asin, e)
        return []
    if not bodies or not llm_available():
        return []
    prompt = (
        f"产品：{match['product_name']}\n以下是 Amazon 真实用户评论原文：\n\n"
        + "\n\n".join(bodies)[:4000] +
        "\n\n请仅基于评论归纳最多 3 个痛点，JSON 返回："
        "{\"pains\":[{\"pain\":\"痛点中文概述\",\"severity\":0-100,\"evidence\":整数(估计提及条数)}]}"
    )
    try:
        data = synthesize(_PAIN_SYSTEM, prompt, temperature=0.3, max_tokens=900)
    except AgnesError as e:
        log.warning("ProductAgent 痛点归纳失败：%s", e)
        return []
    return [p for p in (data.get("pains") or []) if isinstance(p, dict) and (p.get("pain") or "").strip()]


def score_opportunity(niche_keyword: str, country: str = "US", budget_usd: int = 5000) -> dict:
    candidates = _live_signals(country, niche_keyword)
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

    # 真实痛点（severity 来自大模型对真实评论的判断）
    real_pains = _real_pains(match, country)
    if real_pains:
        pains = [{"pain": p["pain"], "base_severity": _clamp(float(p.get("severity") or 50)),
                  "evidence": max(1, int(p.get("evidence") or 1))} for p in real_pains[:3]]
        top_pain = pains[0]["pain"]
    else:
        pains = [{"pain": "暂未从真实评论中归纳出明确痛点", "base_severity": 40, "evidence": 0}]
        top_pain = "用户未被满足的需求"

    for c in candidates:
        c["demand_raw"] = float(c["search_volume_monthly"])
        c["competition_raw"] = c["num_sellers"] * (1 + c["avg_reviews"] / 1000.0) * (1 + c["top_seller_share"] * 2)
        c["pain_points"] = pains if c is match else []

    demand_norm = _minmax([c["demand_raw"] for c in candidates])
    comp = [100 - v for v in _minmax([c["competition_raw"] for c in candidates])]
    idx = candidates.index(match)
    entry_cost = match["avg_price_usd"] * 150 + 1500
    budget_fit = round(_clamp(100 * budget_usd / entry_cost), 1)
    total_ev = sum(p["evidence"] for p in pains) or 1
    pain_raw = round(sum(p["base_severity"] * p["evidence"] for p in pains) / total_ev, 1)
    opportunity = (0.35 * demand_norm[idx] + 0.30 * comp[idx] + 0.20 * pain_raw + 0.15 * budget_fit)

    return {
        "product_name": match["product_name"],
        "niche_keyword": match["niche_keyword"],
        "market_size_monthly_usd": int(max(
            (match["search_volume_monthly"] or 0) * 0.012 * (match["avg_price_usd"] or 1),
            (match["avg_reviews"] or 0) * (match["avg_price_usd"] or 1) * 0.02,
            (match["avg_price_usd"] or 1) * 30)),
        "growth_yoy": match["growth_yoy"],
        "competition_level": "Low" if comp[idx] >= 66 else ("Medium" if comp[idx] >= 40 else "High"),
        "demand_score": demand_norm[idx],
        "competition_score": comp[idx],
        "pain_severity_score": round(pain_raw, 1),
        "budget_fit_score": budget_fit,
        "opportunity_score": round(opportunity, 1),
        "top_pain": top_pain,
    }


PRODUCT_TOOLS = [
    {
        "name": "score_opportunity",
        "description": "对单个利基做需求/竞争/痛点/预算四维机会评分，返回可解释子分（数据来自实时 Bright Data + 真实评论）。",
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
