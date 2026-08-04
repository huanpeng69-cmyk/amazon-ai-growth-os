"""Risk Agent —— 输入 / 输出 Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class RiskItem(BaseModel):
    factor: str
    severity: float = Field(..., ge=0, le=100, description="风险严重度 0-100")
    description: str
    mitigation: str


class RiskInput(BaseModel):
    product_name: str
    country: str = "US"
    net_margin: float = Field(..., description="单件净利率（来自 Profit Agent）")
    selling_price: float = 0.0
    ad_acos: float = 0.15
    payback_months: Optional[float] = None
    supply_chain_connected: bool = False
    competition_level: Optional[str] = Field(None, description="low / medium / high")


class RiskOutput(BaseModel):
    risk_level: str            # low / medium / high
    risk_score: float          # 0-100，越高越危险
    risks: List[RiskItem]
    warning_text: str
