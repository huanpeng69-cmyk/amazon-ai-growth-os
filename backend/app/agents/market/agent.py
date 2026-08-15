"""Market Agent —— 执行器（蓝海挖掘）。

数据源优先级：
1. **Bright Data MCP（amazon_research）**：实时抓取 Amazon SERP，返回真实商品
   （价格、评分、评论数均为真实数据）。
2. **DB fixture（dal.get_market）**：降级方案，当 Bright Data 不可用时回退。

评分逻辑不变：市场规模 → 竞争度 → 痛点 → 综合评分 → 进入建议 → 排序。
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from app.agents.market.schemas import (
    MarketInput,
    MarketOutput,
    PainPoint,
    ProductOpportunity,
)
from app.agents.market.tools import MARKET_TOOLS

log = logging.getLogger(__name__)


def _minmax(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [50.0 for _ in values]
    return [round((v - lo) / (hi - lo) * 100, 1) for v in values]


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _competition_level(score: float) -> str:
    return "Low" if score >= 66 else ("Medium" if score >= 40 else "High")


def _recommendation(score: float, comp_level: str, monthly: int,
                    top_pain: str, budget_fit: float) -> str:
    if score >= 75:
        tier = "强烈建议进入"
    elif score >= 60:
        tier = "建议进入"
    elif score >= 45:
        tier = "可选择性进入，需差异化定位"
    else:
        tier = "暂不推荐，竞争激烈且需求有限"
    fit = ("预算充足" if budget_fit >= 80
           else "预算偏紧，建议小批量测款" if budget_fit >= 50
           else "预算不足，建议提高预算或选低价利基")
    return (f"{tier}。该类目竞争度 {comp_level}，月规模约 ${monthly:,}；"
            f"核心突破口是「{top_pain}」，以差异化卖点切入。{fit}。")


def _estimate_growth(reviews: int, price: float) -> float:
    """基于评论热度与价格带估算年增速代理值（Bright Data 不提供真实 YoY）。

    逻辑：高评论量 + 中低价 = 高增长赛道（大众消费、周转快）；
          低评论量 + 高价 = 成熟/小众赛道（增速低）。
    返回 0.0 ~ 0.45 之间的浮点数（即 0% ~ 45%）。
    """
    if reviews <= 0 and price <= 0:
        return 0.05  # 无数据时给一个保守默认值
    # 评论热度分 (0~1)：10000+ 评论视为热门
    heat = min(reviews / 10000.0, 1.0)
    # 价格带因子：$10-$50 最活跃，过高或过低都降权
    if price <= 0:
        price_factor = 0.5
    elif 10 <= price <= 50:
        price_factor = 1.0
    elif 50 < price <= 100:
        price_factor = 0.8
    else:
        price_factor = 0.6
    return round(min(heat * price_factor * 0.45, 0.45), 3)


def _extract_features(title: str) -> list[str]:
    """从产品标题提取特征词（用于合成 pain point）。"""
    # 去掉品牌名和常见修饰词后，按分隔符拆分
    junk = re.compile(
        r"\b(the|a|an|new|upgraded?|innovations?|award.?winner?|premium|"
        r"automatic|stainless|steel|bpa.?free|food.?grade|large|extra|"
        r"dual|compact|original|pro|plus|xl|set|pack|with|for)\b",
        re.I,
    )
    clean = junk.sub("", title)
    parts = re.split(r"[,|/·\-\–\—()（）【】\[\]]", clean)
    return [p.strip() for p in parts if len(p.strip()) > 2]


def _build_pain_points(title: str, reviews: int) -> list[dict]:
    """从产品标题 + 评论数合成痛点条目（无 VOC 时降级用）。"""
    feats = _extract_features(title)[:5]
    pains = []
    for i, f in enumerate(feats[:3]):
        severity = round(max(40, 80 - i * 15), 1)
        evidence = max(1, int(reviews / (i + 1) * 0.01)) if reviews else 1
        pains.append({"pain": f, "base_severity": severity, "evidence": evidence})
    if not pains:
        pains.append({"pain": "用户未被满足的需求", "base_severity": 50, "evidence": 1})
    return pains


class MarketAgent:
    name = "market"
    description = "蓝海市场挖掘：国家 + 类目 + 预算 → Top-N 潜力产品"

    def run(self, inp: MarketInput) -> MarketOutput:
        candidates = self._fetch(inp)

        # 市场规模 & 需求原始值
        for c in candidates:
            price = c.get("avg_price_usd") or 0.0
            reviews = c.get("avg_reviews") or 0
            c["market_size_monthly_usd"] = int(
                max(reviews * price * 0.02, price * 30)
            )  # 月规模 ≈ 评论量 × 单价 × 转化率
            c["demand_raw"] = float(
                c.get("search_volume_monthly") or reviews * 10 or 1
            )
            c["competition_raw"] = (
                c.get("num_sellers", 0) * (1 + reviews / 2000.0) *
                (1 + c.get("top_seller_share", 0.15) * 2)
            )
            total_ev = sum(p["evidence"] for p in c["pain_points"]) or 1
            c["pain_severity_raw"] = round(
                sum(p["base_severity"] * p["evidence"]
                    for p in c["pain_points"]) / total_ev, 1
            )
            c["top_pain_points"] = sorted(
                c["pain_points"], key=lambda p: p["base_severity"], reverse=True
            )[:3]

        demand_norm = _minmax([c["demand_raw"] for c in candidates])
        comp_norm = [100 - v for v in _minmax([c["competition_raw"] for c in candidates])]

        for i, c in enumerate(candidates):
            price = c.get("avg_price_usd") or 0.0
            entry_cost = price * 150 + 1500
            budget_fit = round(_clamp(100 * inp.budget_usd / entry_cost), 1)
            opportunity = (0.35 * demand_norm[i] + 0.30 * comp_norm[i]
                           + 0.20 * c["pain_severity_raw"] + 0.15 * budget_fit)
            c["demand_score"] = demand_norm[i]
            c["competition_score"] = comp_norm[i]
            c["pain_severity_score"] = c["pain_severity_raw"]
            c["budget_fit_score"] = budget_fit
            c["opportunity_score"] = round(opportunity, 1)
            c["competition_level"] = _competition_level(comp_norm[i])

        ranked = sorted(candidates, key=lambda c: c["opportunity_score"], reverse=True)[: inp.top_n]
        opportunities: list[ProductOpportunity] = []
        for i, c in enumerate(ranked, start=1):
            top_pain = c["top_pain_points"][0]["pain"] if c["top_pain_points"] else "用户未被满足的需求"
            opportunities.append(ProductOpportunity(
                rank=i,
                product_name=c["product_name"],
                niche_keyword=c.get("niche_keyword") or inp.category,
                market_size_monthly_usd=c["market_size_monthly_usd"],
                market_size_growth_yoy=c.get("growth_yoy", 0.0),
                competition_level=c["competition_level"],
                competition_score=c["competition_score"],
                demand_score=c["demand_score"],
                pain_severity_score=c["pain_severity_score"],
                budget_fit_score=c["budget_fit_score"],
                top_pain_points=[PainPoint(pain=p["pain"], severity=p["base_severity"],
                                            evidence=p["evidence"])
                                 for p in c["top_pain_points"]],
                opportunity_score=c["opportunity_score"],
                entry_recommendation=_recommendation(
                    c["opportunity_score"], c["competition_level"],
                    c["market_size_monthly_usd"], top_pain, c["budget_fit_score"]),
            ))
        return MarketOutput(
            country=inp.country, category=inp.category,
            budget_usd=inp.budget_usd, opportunities=opportunities)

    # ── 数据采集 ──
    def _fetch(self, inp: MarketInput) -> list[dict]:
        """优先走 Bright Data 实时抓取；失败时降级 DB fixture。"""
        live_candidates = self._try_live(inp)
        if live_candidates is not None:
            log.info("MarketAgent: 使用 Bright Data 实时数据 (%d 产品)", len(live_candidates))
            return live_candidates
        # 降级：DB fixture
        log.info("MarketAgent: Bright Data 不可用，降级 DB fixture")
        search = next(t for t in MARKET_TOOLS if t["name"] == "search_market")["handler"]
        return search(inp.country, inp.category, pool_size=24)

    def _try_live(self, inp: MarketInput) -> Optional[list[dict]]:
        """尝试通过 Bright Data MCP 的 amazon_research 获取实时商品数据。

        返回 None 表示不可用（调用方应降级），不抛异常。
        """
        from app.mcp.brightdata_client.exceptions import BrightDataError
        from app.tools.base import ToolNotConfigured
        try:
            from app.mcp.tools.amazon_research import amazon_research
            res = amazon_research(
                keyword=inp.category,
                country=inp.country,
                limit=max(inp.top_n, 12),  # 多拉几个以便排序后截断
            )
        except (BrightDataError, ToolNotConfigured, ImportError):
            return None

        products = (res or {}).get("products") or []
        if not products:
            return None

        out = []
        seen_titles: set[str] = set()
        for p in products:
            name = (p.get("title") or "").strip()
            if not name or name in seen_titles:
                continue
            seen_titles.add(name)
            price_raw = p.get("price")
            rating = p.get("rating")
            reviews = p.get("reviews")

            # amazon_research 的 price 经 _money() 归一化为「纯数值字符串」（如 "19.99"），
            # 此处需转成 float；None/空串/解析失败则记 0。
            price = 0.0
            if price_raw not in (None, ""):
                try:
                    price = float(str(price_raw).replace("$", "").replace(",", ""))
                except (TypeError, ValueError):
                    price = 0.0

            out.append({
                "product_name": name,
                "niche_keyword": inp.category,
                "search_volume_monthly": (reviews or 0) * 8,  # 评论量 × 系数 ≈ 搜索量代理
                "avg_price_usd": price,
                "num_sellers": len(products),  # 样本内不同 ASIN 数 ≈ 卖家数代理
                "avg_reviews": reviews if isinstance(reviews, (int, float)) else 0,
                "top_seller_share": 0.15,  # 无头部占比数据时用保守默认值
                "growth_yoy": _estimate_growth(reviews or 0, price),  # 基于评论热度估算增速代理值
                "pain_points": _build_pain_points(name, reviews or 0),
            })
        return out if out else None
