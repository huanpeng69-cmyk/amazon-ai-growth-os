"""Sales Forecast Agent —— 执行器。

销量预测 + 回本周期。

此前使用硬编码的「类目基准需求常量」(pets=320, kitchen=280, ...) 作为月销量，
属于编造数据。现改为：
- 优先使用用户/上游提供的真实月销量（provided_units）；
- 否则以 **Bright Data 实时抓取**的头部商品评论活跃度作为真实市场需求信号（相对基准），
  不再套用固定类目常量；
- 无任何真实信号时，明确告知「需接入真实销量数据源」，仅给带强声明的规划假设值。
"""
from __future__ import annotations

import logging

from app.agents.sales_forecast.schemas import SalesForecastInput, SalesForecastOutput

log = logging.getLogger(__name__)

_COMP_LEVEL_FACTOR = {"low": 1.15, "medium": 0.9, "high": 0.7}


def _real_demand_base(category: str | None, country: str) -> int | None:
    """以 Bright Data 实时头部商品的评论活跃度作为真实市场需求信号（相对基准）。"""
    if not category:
        return None
    try:
        from app.mcp.brightdata_client.exceptions import BrightDataError
        from app.tools.base import ToolNotConfigured
        from app.mcp.tools.amazon_research import amazon_research
        res = amazon_research(keyword=category, country=country, limit=10)
    except (BrightDataError, ToolNotConfigured, ImportError):
        return None
    products = (res or {}).get("products") or []
    if not products:
        return None
    total_reviews = sum((p.get("reviews") or 0) for p in products)
    if total_reviews <= 0:
        return None
    # 真实市场活跃度（头部商品评论总量 / 商品数）作为相对需求信号，映射到合理区间
    avg_activity = total_reviews / len(products)
    base = int(avg_activity * 0.5)
    return max(20, min(5000, base))


class SalesForecastAgent:
    name = "sales_forecast"
    description = "销量预测 + 回本周期：真实需求信号（用户提供/Bright Data）+ 透明规划假设"

    def run(self, inp: SalesForecastInput) -> SalesForecastOutput:
        if inp.provided_units:
            units = inp.provided_units
            basis = "采用用户/上游提供的真实月销量作为确定值。"
        else:
            base = _real_demand_base(inp.category, inp.country)
            if base is None:
                units = 200  # 规划占位值
                basis = (
                    "⚠️ 未获取到真实需求信号（未提供销量，且 Bright Data 实时抓取不可用）。"
                    "以下为带强声明的规划假设值，仅供参考；接入真实销量数据源"
                    "（如 Amazon Business Report / 广告报表）后可替换为实测值。"
                )
            else:
                ref = inp.competitor_price or max(inp.selling_price * 0.95, 1.0)
                price_factor = max(0.4, min(2.2, ref / inp.selling_price))
                ad_factor = min(1.4, 0.7 + inp.ad_acos * 2.0)
                comp_factor = _COMP_LEVEL_FACTOR.get((inp.competition_level or "medium").lower(), 0.9)
                units = int(round(base * price_factor * ad_factor * comp_factor))
                units = max(20, min(5000, units))
                basis = (
                    f"基于 Bright Data 实时抓取头部商品的真实市场活跃度（评论量信号）得到的相对需求基准 {base} 件/月，"
                    f"× 价格竞争力 {price_factor:.2f} × 广告流量 {ad_factor:.2f} × 竞争强度 {comp_factor:.2f}"
                    f" = 约 {units} 件/月（透明规划假设，非实测销量）。"
                )

        net = inp.net_profit_per_unit
        break_even = (inp.monthly_fixed_cost / net) if net > 0 else float("inf")

        monthly_op = net * units - inp.monthly_fixed_cost
        payback = None
        if inp.initial_investment > 0 and monthly_op > 0:
            payback = round(inp.initial_investment / monthly_op, 1)

        return SalesForecastOutput(
            estimated_monthly_units=units,
            break_even_monthly_units=round(break_even, 1) if break_even != float("inf") else -1.0,
            payback_months=payback,
            basis=basis,
        )
