"""Sales Forecast Agent —— 执行器。"""
from __future__ import annotations

from app.agents.sales_forecast.schemas import SalesForecastInput, SalesForecastOutput

# 各类目基准月需求（单位：件），启发式常量
_CATEGORY_DEMAND = {
    "pets": 320, "pet": 320, "kitchen": 280, "home": 240, "beauty": 220,
    "electronics": 200, "toys": 300, "sports": 260, "outdoor": 230, "baby": 260,
    "garden": 220, "office": 180,
}
_COMP_LEVEL_FACTOR = {"low": 1.15, "medium": 0.9, "high": 0.7}


def _category_base(category: str | None) -> int:
    if not category:
        return 260
    c = category.lower()
    for k, v in _CATEGORY_DEMAND.items():
        if k in c:
            return v
    return 260


class SalesForecastAgent:
    name = "sales_forecast"
    description = "销量预测 + 回本周期：基于价格/广告/类目需求/竞争强度的启发式估算"

    def run(self, inp: SalesForecastInput) -> SalesForecastOutput:
        if inp.provided_units:
            units = inp.provided_units
            basis = "采用用户/上游提供的月销量作为确定值。"
        else:
            base = _category_base(inp.category)
            # 价格竞争力：以竞品价或类目参考价为锚，越便宜相对销量越高
            ref = inp.competitor_price or max(inp.selling_price * 0.95, 1.0)
            price_factor = max(0.4, min(2.2, ref / inp.selling_price))
            # 广告投入带来的流量因子
            ad_factor = min(1.4, 0.7 + inp.ad_acos * 2.0)
            comp_factor = _COMP_LEVEL_FACTOR.get((inp.competition_level or "medium").lower(), 0.9)
            units = int(round(base * price_factor * ad_factor * comp_factor))
            units = max(20, min(5000, units))
            basis = (
                f"启发式估算：类目基准需求 {base} 件/月 × 价格竞争力 {price_factor:.2f} "
                f"× 广告流量 {ad_factor:.2f} × 竞争强度 {comp_factor:.2f} = {units} 件/月。"
                "接入真实销量数据源后可替换为实测值。"
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
