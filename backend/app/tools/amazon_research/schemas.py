"""amazon_research 工具 —— 输入/输出 JSON 契约（Pydantic → JSON Schema）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PainPointOut(BaseModel):
    pain: str
    severity: float
    evidence: int


class ProductOpportunityOut(BaseModel):
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
    top_pain_points: list[PainPointOut]
    opportunity_score: float
    entry_recommendation: str


class AmazonResearchInput(BaseModel):
    country: str = Field(..., description="Amazon 站点国家代码，如 US / DE / JP")
    category: str = Field(..., description="Amazon 类目或利基关键词")
    budget_usd: float = Field(5000, description="进入预算（美元）")
    top_n: int = Field(10, description="返回 Top-N 潜力产品", ge=1, le=50)


class AmazonResearchOutput(BaseModel):
    country: str
    category: str
    budget_usd: float
    opportunities: list[ProductOpportunityOut]
