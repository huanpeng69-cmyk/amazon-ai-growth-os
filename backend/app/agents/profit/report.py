"""利润报告编排：串联 Profit / Sales Forecast / Risk 三个 Agent。

输出统一的产品盈利报告（Product Profitability Report）。
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel

from app.agents.profit.agent import ProfitAgent
from app.agents.profit.schemas import ProfitInput, ProfitOutput
from app.agents.risk.agent import RiskAgent
from app.agents.risk.schemas import RiskInput
from app.agents.sales_forecast.agent import SalesForecastAgent
from app.agents.sales_forecast.schemas import SalesForecastInput, SalesForecastOutput
from app.agents.risk.schemas import RiskOutput


class ProfitReport(BaseModel):
    product_name: str
    country: str
    currency: str = "USD"
    generated_at: str
    input: dict
    profit: ProfitOutput
    forecast: SalesForecastOutput
    risk: RiskOutput
    cost_source: str


def build_profit_report(inp: ProfitInput) -> ProfitReport:
    profit = ProfitAgent().run(inp)
    net = profit.per_unit.net_profit

    forecast = SalesForecastAgent().run(SalesForecastInput(
        product_name=inp.product_name,
        country=inp.country,
        selling_price=inp.selling_price,
        ad_acos=inp.ad_acos,
        category=inp.category,
        competitor_price=inp.competitor_price,
        competition_level=inp.competition_level,
        net_profit_per_unit=net,
        monthly_fixed_cost=inp.monthly_fixed_cost,
        initial_investment=inp.initial_investment,
        provided_units=inp.monthly_units,
    ))
    # 用预测销量回填 Profit 的月维度（若用户未提供）
    if not inp.monthly_units:
        profit.monthly_units = forecast.estimated_monthly_units
        profit.monthly_gross_profit = round(profit.per_unit.gross_profit * forecast.estimated_monthly_units, 2)
        profit.monthly_net_profit = round(net * forecast.estimated_monthly_units, 2)
        profit.monthly_net_operating = round(profit.monthly_net_profit - inp.monthly_fixed_cost, 2)

    risk = RiskAgent().run(RiskInput(
        product_name=inp.product_name,
        country=inp.country,
        net_margin=profit.per_unit.net_margin,
        selling_price=inp.selling_price,
        ad_acos=inp.ad_acos,
        payback_months=forecast.payback_months,
        supply_chain_connected=(inp.cost_source == "supply_chain"),
        competition_level=inp.competition_level,
    ))

    return ProfitReport(
        product_name=inp.product_name,
        country=inp.country,
        currency=inp.currency,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        input=inp.model_dump(),
        profit=profit,
        forecast=forecast,
        risk=risk,
        cost_source=inp.cost_source or "manual",
    )
