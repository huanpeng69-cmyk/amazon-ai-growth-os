"""amazon_research 后端适配器。

- MockBackend：组合调用现有 MarketAgent（确定性评分流水线），离线可演示。
- McpBackend / ApiBackend：未来接入 Bright Data / Sorftime / Sif 的 MCP/API，
  仅保留接口骨架，替换时无需改动调用方。
"""
from __future__ import annotations

from app.tools.base import BackendType, ToolBackend, ToolNotConfigured
# 复用现有能力（组合，而非复制源码）
from app.agents.market.agent import MarketAgent
from app.agents.market.schemas import MarketInput


class AmazonResearchBackend(ToolBackend):
    backend_type = BackendType.MOCK  # 配置键仍为 mock；数据已改为真实 Connector 来源

    def execute(self, params: dict) -> dict:
        return MarketAgent().run(MarketInput(**params)).model_dump()


class McpAmazonResearchBackend(ToolBackend):
    backend_type = BackendType.MCP

    def execute(self, params: dict) -> dict:
        # 链路：Agent → amazon_research 工具(MCP 后端)
        #        → mcp.tools.amazon_research (Tool 层)
        #        → BrightDataMCPClient (MCP 层) → Bright Data
        from app.mcp.tools.amazon_research import amazon_research

        keyword = params.get("category") or params.get("keyword") or ""
        country = params.get("country", "US")
        top_n = int(params.get("top_n", 10))
        budget = float(params.get("budget_usd", 5000))
        try:
            res = amazon_research(keyword=keyword, country=country, limit=top_n)
        except Exception as e:  # 降级提示，不让 Agent 链路崩溃
            raise ToolNotConfigured(f"Bright Data MCP 调用失败：{e}")
        products = res.get("products") or []
        if not products:
            raise ToolNotConfigured(
                f"Bright Data 未返回与 '{keyword}' 相关的商品（请检查关键词 / 凭证）"
            )
        opportunities = [_product_to_opportunity(p, i, keyword, budget) for i, p in enumerate(products[:top_n])]
        return {
            "country": country,
            "category": keyword,
            "budget_usd": budget,
            "opportunities": opportunities,
        }


def _pf(v) -> float:
    if v is None:
        return 0.0
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _pi(v) -> int:
    f = _pf(v)
    return int(f) if f else 0


def _product_to_opportunity(p: dict, idx: int, keyword: str, budget: float) -> dict:
    """把 Bright Data 商品（统一 JSON）映射为蓝海机会评分结构。

    评分为基于真实抓取字段（价格/评论数/评分）的启发式派生，
    非随机编造；VOC 痛点相关维度在缺 VOC 数据时置 0。
    """
    title = p.get("title") or ""
    price = _pf(p.get("price"))
    reviews = _pi(p.get("reviews"))
    rating = _pf(p.get("rating"))
    category = p.get("category") or keyword

    competition_score = min(reviews / 5000.0, 1.0)
    demand_score = min(reviews / 3000.0, 1.0)
    competition_level = "high" if competition_score > 0.66 else ("medium" if competition_score > 0.33 else "low")
    budget_fit = max(0.0, min(1.0, (budget * 0.1) / price)) if price > 0 else 0.5
    rating_fit = (rating / 5.0) if rating > 0 else 0.5
    opportunity_score = round(
        0.35 * demand_score + 0.30 * (1 - competition_score) + 0.20 * budget_fit + 0.15 * rating_fit,
        3,
    )
    if opportunity_score >= 0.7:
        rec = "强烈建议进入：需求强、竞争可控、预算匹配"
    elif opportunity_score >= 0.5:
        rec = "可考虑进入：需差异化卖点以突围"
    else:
        rec = "暂不建议：竞争激烈或需求不足"

    return {
        "rank": idx + 1,
        "product_name": title,
        "niche_keyword": category,
        "market_size_monthly_usd": int(price * max(reviews, 1) * 0.2),
        "market_size_growth_yoy": 0.0,
        "competition_level": competition_level,
        "competition_score": round(competition_score, 3),
        "demand_score": round(demand_score, 3),
        "pain_severity_score": 0.0,
        "budget_fit_score": round(budget_fit, 3),
        "top_pain_points": [],
        "opportunity_score": opportunity_score,
        "entry_recommendation": rec,
    }


class ApiAmazonResearchBackend(ToolBackend):
    backend_type = BackendType.API

    def execute(self, params: dict) -> dict:
        raise ToolNotConfigured(
            "amazon_research API 后端未配置：设置 AMAZON_RESEARCH_API_BASE 与 "
            "API_KEY 后接入 SellerSprite / Sorftime REST API"
        )
