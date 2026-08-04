"""Market Agent —— 输入/输出 Schema。"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class MarketInput(BaseModel):
    country: str = Field(..., description="站点国家代码 US/DE/JP/UK ...")
    category: str = Field(..., description="Amazon 类目")
    budget_usd: int = Field(..., gt=0, description="入市预算（美元）")
    top_n: int = Field(10, ge=1, le=25, description="返回潜力产品数量")


class PainPoint(BaseModel):
    pain: str
    severity: float = Field(..., ge=0, le=100)
    evidence: int = Field(..., ge=0, description="评论中提及次数")


class ProductOpportunity(BaseModel):
    rank: int
    product_name: str
    niche_keyword: str
    market_size_monthly_usd: int
    market_size_growth_yoy: float
    competition_level: str
    competition_score: float
    demand_score: float
    pain_severity_score: float
    budget_fit_score: float
    top_pain_points: List[PainPoint]
    opportunity_score: float
    entry_recommendation: str


class MarketOutput(BaseModel):
    country: str
    category: str
    budget_usd: int
    opportunities: List[ProductOpportunity]
