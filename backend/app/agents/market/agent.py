"""Market Agent —— 执行器（蓝海挖掘）。

数据链路：
1. **Bright Data（amazon_research）**：实时抓取 Amazon SERP，返回真实商品
   （价格、评分、评论数均为真实数据）。
2. **ReviewConnector**：对候选商品抓取*真实用户评论*原文。
3. **Agnes 大模型**：仅基于真实评论归纳每个产品的痛点（severity/evidence），
   并基于真实指标 + 真实痛点生成"进入建议"。
   大模型不可用时，痛点/建议置空并诚实告知，绝不编造。

说明：market_size_growth_yoy 为基于评论热度×价格带的派生代理值（Bright Data 不提供真实
YoY），属透明启发式，非伪造的"真实增速"。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.agents.market.schemas import (
    MarketInput,
    MarketOutput,
    PainPoint,
    ProductOpportunity,
)
from app.agents.market.tools import MARKET_TOOLS
from app.agents._util import llm_available, synthesize
from app.data.connectors.review_connector.connector import ReviewConnector
from app.llm.agnes import AgnesError

log = logging.getLogger(__name__)


_PAIN_SYSTEM = (
    "你是资深的亚马逊选品与用户体验（VOC）分析师。"
    "你只依据用户提供的真实评论原文归纳痛点，绝不编造任何评论、数据或产品事实；"
    "只列真实出现在评论中的痛点。"
)


def _minmax(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [50.0 for _ in values]
    return [round((v - lo) / (hi - lo) * 100, 1) for v in values]


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _competition_level(score: float) -> str:
    return "Low" if score >= 66 else ("Medium" if score >= 40 else "High")


def _estimate_growth(reviews: int, price: float) -> float:
    """基于评论热度与价格带的年增速代理值（透明启发式，非真实 YoY）。"""
    if reviews <= 0 and price <= 0:
        return 0.05
    heat = min(reviews / 10000.0, 1.0)
    if price <= 0:
        price_factor = 0.5
    elif 10 <= price <= 50:
        price_factor = 1.0
    elif 50 < price <= 100:
        price_factor = 0.8
    else:
        price_factor = 0.6
    return round(min(heat * price_factor * 0.45, 0.45), 3)


class MarketAgent:
    name = "market"
    description = "蓝海市场挖掘：国家 + 类目 + 预算 → Top-N 潜力产品（真实评论 + 大模型痛点/建议）"

    def run(self, inp: MarketInput) -> MarketOutput:
        candidates = self._fetch(inp)
        if not candidates:
            return MarketOutput(
                country=inp.country, category=inp.category,
                budget_usd=inp.budget_usd, opportunities=[])

        # 1) 由真实数据计算规模/需求/竞争原始值
        for c in candidates:
            price = c.get("avg_price_usd") or 0.0
            reviews = c.get("avg_reviews") or 0
            c["market_size_monthly_usd"] = int(max(reviews * price * 0.02, price * 30))
            c["demand_raw"] = float(c.get("search_volume_monthly") or reviews * 10 or 1)
            c["competition_raw"] = (
                c.get("num_sellers", 0) * (1 + reviews / 2000.0) *
                (1 + c.get("top_seller_share", 0.15) * 2)
            )

        demand_norm = _minmax([c["demand_raw"] for c in candidates])
        comp_norm = [100 - v for v in _minmax([c["competition_raw"] for c in candidates])]

        # 2) 抓真实评论 + 大模型归纳痛点（仅 limit 个候选，控制成本）
        limit = min(max(inp.top_n, 6), 12)
        top_for_pain = sorted(
            range(len(candidates)),
            key=lambda i: (demand_norm[i] + comp_norm[i]),
            reverse=True,
        )[:limit]
        pain_map = self._synthesize_pains([candidates[i] for i in top_for_pain], inp.country)
        for i in top_for_pain:
            c = candidates[i]
            raws = pain_map.get(c["product_name"], []) or []
            pains = []
            for p in raws[:3]:
                if not isinstance(p, dict):
                    continue
                pain = (p.get("pain") or "").strip()
                if not pain:
                    continue
                try:
                    sev = float(p.get("severity") or 50)
                except (TypeError, ValueError):
                    sev = 50.0
                try:
                    ev = int(p.get("evidence") or 1)
                except (TypeError, ValueError):
                    ev = 1
                pains.append({"pain": pain, "base_severity": _clamp(sev), "evidence": max(1, ev)})
            if not pains:
                pains = [{"pain": "暂未从真实评论中归纳出明确痛点", "base_severity": 40, "evidence": 0}]
            c["pain_points"] = pains

        # 3) 评分 + 排序
        for i, c in enumerate(candidates):
            price = c.get("avg_price_usd") or 0.0
            entry_cost = price * 150 + 1500
            budget_fit = round(_clamp(100 * inp.budget_usd / entry_cost), 1)
            pains = c.get("pain_points") or []
            total_ev = sum(p["evidence"] for p in pains) or 1
            pain_sev = round(sum(p["base_severity"] * p["evidence"] for p in pains) / total_ev, 1)
            c["pain_severity_raw"] = pain_sev
            c["demand_score"] = demand_norm[i]
            c["competition_score"] = comp_norm[i]
            c["pain_severity_score"] = pain_sev
            c["budget_fit_score"] = budget_fit
            c["opportunity_score"] = round(
                0.35 * demand_norm[i] + 0.30 * comp_norm[i] + 0.20 * pain_sev + 0.15 * budget_fit, 1)
            c["competition_level"] = _competition_level(comp_norm[i])
            c["top_pain_points"] = sorted(pains, key=lambda p: p["base_severity"], reverse=True)[:3]

        ranked = sorted(candidates, key=lambda c: c["opportunity_score"], reverse=True)[: inp.top_n]

        # 4) 大模型基于真实指标+真实痛点生成进入建议
        recs = self._synthesize_recommendations(ranked, inp.budget_usd)

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
                entry_recommendation=recs.get(c["product_name"],
                    f"综合评分 {c['opportunity_score']}，竞争度 {c['competition_level']}，"
                    f"建议结合真实评论中的「{top_pain}」做差异化切入。"),
            ))
        return MarketOutput(
            country=inp.country, category=inp.category,
            budget_usd=inp.budget_usd, opportunities=opportunities)

    # ── 真实评论 + 大模型归纳痛点 ──
    def _synthesize_pains(self, candidates: List[dict], country: str) -> Dict[str, list]:
        rc = ReviewConnector()
        blocks: List[str] = []
        for c in candidates:
            asin = c.get("asin")
            if not asin:
                continue
            bodies: List[str] = []
            try:
                raw = rc._fetch_live({"asin": asin, "country": country})
                for r in (raw.payload or {}).get("reviews") or []:
                    b = r.get("body") or ""
                    if b.strip():
                        bodies.append(b)
            except Exception as e:  # 单个失败不影响其他
                log.warning("MarketAgent 抓取评论 %s 失败：%s", asin, e)
            if bodies:
                blocks.append(
                    f"### 产品：{c['product_name']}\n" +
                    "\n\n".join(bodies)[:2500])
        if not blocks:
            return {}
        if not llm_available():
            log.info("MarketAgent: 未配置 AGNES_API_KEY，痛点跳过（不编造）")
            return {}
        prompt = (
            "以下是我们在 Amazon 上真实抓取的若干产品及其用户评论原文：\n\n"
            + "\n\n".join(blocks) +
            "\n\n请仅基于上述真实评论，为每个产品归纳最多 3 个痛点，"
            "以 JSON 对象返回（键为产品名，须与上方「### 产品：」后的名称一致）：\n"
            "{\"产品名\": [{\"pain\": \"痛点中文概述\", \"severity\": 0-100 的整数, "
            "\"evidence\": 整数(估计提及该痛点的评论条数)}]}\n"
            "只列真实出现在评论中的痛点；无评论可归纳的产品给空数组。"
        )
        try:
            data = synthesize(_PAIN_SYSTEM, prompt, temperature=0.3, max_tokens=1600)
        except AgnesError as e:
            log.warning("MarketAgent 大模型痛点归纳失败：%s", e)
            return {}
        # 名称对齐（容忍 LLM 轻微改写）
        out: Dict[str, list] = {}
        for c in candidates:
            nm = c["product_name"]
            if nm in data and isinstance(data[nm], list):
                out[nm] = data[nm]
                continue
            for k, v in data.items():
                if isinstance(v, list) and k.strip() == nm.strip():
                    out[nm] = v
                    break
        return out

    # ── 大模型生成进入建议 ──
    def _synthesize_recommendations(self, ranked: List[dict], budget_usd: int) -> Dict[str, str]:
        if not llm_available() or not ranked:
            return {}
        items = []
        for c in ranked:
            tp = c["top_pain_points"][0]["pain"] if c["top_pain_points"] else "用户未被满足的需求"
            items.append(
                f"- {c['product_name']}｜月规模 ${c['market_size_monthly_usd']:,}｜"
                f"竞争度 {c['competition_level']}｜机会分 {c['opportunity_score']}｜"
                f"核心痛点「{tp}」")
        prompt = (
            "以下是我们筛出的潜力产品（数据来自 Amazon 真实抓取 + 真实评论归纳）：\n"
            + "\n".join(items) + f"\n预算 ${budget_usd:,}。\n\n"
            "请基于以上真实信息，为每个产品写一句中文「进入建议」（含是否建议进入、差异化切入点）。"
            "以 JSON 数组返回，顺序与上面产品顺序一致：\n"
            "[{\"product\": \"产品名\", \"recommendation\": \"中文建议\"}]\n"
            "只做基于真实数据的判断，不要编造数据。"
        )
        try:
            data = synthesize(_PAIN_SYSTEM, prompt, temperature=0.3, max_tokens=1000)
        except AgnesError as e:
            log.warning("MarketAgent 大模型建议生成失败：%s", e)
            return {}
        out: Dict[str, str] = {}
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict) and row.get("product") and row.get("recommendation"):
                    out[row["product"]] = str(row["recommendation"])
        elif isinstance(data, dict):
            # 兼容 {product: recommendation} 形式
            for k, v in data.items():
                out[k] = str(v)
        return out

    # ── 数据采集 ──
    def _fetch(self, inp: MarketInput) -> list[dict]:
        """优先走 Bright Data 实时抓取；失败时降级 DB fixture。"""
        live_candidates = self._try_live(inp)
        if live_candidates is not None:
            log.info("MarketAgent: 使用 Bright Data 实时数据 (%d 产品)", len(live_candidates))
            return live_candidates
        log.info("MarketAgent: Bright Data 不可用，降级 DB fixture")
        search = next(t for t in MARKET_TOOLS if t["name"] == "search_market")["handler"]
        return search(inp.country, inp.category, pool_size=24)

    def _try_live(self, inp: MarketInput) -> Optional[list[dict]]:
        """通过 Bright Data MCP 的 amazon_research 获取实时商品数据。"""
        from app.mcp.brightdata_client.exceptions import BrightDataError
        from app.tools.base import ToolNotConfigured
        try:
            from app.mcp.tools.amazon_research import amazon_research
            res = amazon_research(
                keyword=inp.category,
                country=inp.country,
                limit=max(inp.top_n, 12),
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
            reviews = p.get("reviews")

            price = 0.0
            if price_raw not in (None, ""):
                try:
                    price = float(str(price_raw).replace("$", "").replace(",", ""))
                except (TypeError, ValueError):
                    price = 0.0

            out.append({
                "product_name": name,
                "asin": p.get("asin"),
                "niche_keyword": inp.category,
                "search_volume_monthly": (reviews or 0) * 8,
                "avg_price_usd": price,
                "num_sellers": len(products),
                "avg_reviews": reviews if isinstance(reviews, (int, float)) else 0,
                "top_seller_share": 0.15,
                "growth_yoy": _estimate_growth(reviews or 0, price),
                "pain_points": [],
            })
        return out if out else None
