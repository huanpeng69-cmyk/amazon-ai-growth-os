"""Sales Forecast Agent —— 输入 / 输出 Schema。

销量预测基于「价格竞争力 / 广告投入 / 类目需求 / 竞争强度」的启发式估算，
并非真实销售数据；接入真实销量数据源（如 Amazon 业务报告 / 供应链接口）后可替换。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SalesForecastInput(BaseModel):
    product_name: str
    country: str = "US"
    selling_price: float = Field(..., gt=0)
    ad_acos: float = Field(0.15, ge=0, le=1)
    category: Optional[str] = None
    competitor_price: Optional[float] = None
    competition_level: Optional[str] = Field(None, description="low / medium / high")
    net_profit_per_unit: float = Field(..., description="来自 Profit Agent 的单件净利润")
    monthly_fixed_cost: float = 0.0
    initial_investment: float = 0.0
    provided_units: Optional[int] = Field(None, ge=0, description="用户/上游提供的月销量，优先使用")


class SalesForecastOutput(BaseModel):
    estimated_monthly_units: int
    break_even_monthly_units: float
    payback_months: Optional[float] = None
    basis: str
