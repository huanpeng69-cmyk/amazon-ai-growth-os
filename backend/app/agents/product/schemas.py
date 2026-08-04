"""Product Agent —— 输入/输出 Schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProductInput(BaseModel):
    niche_keyword: str = Field(..., description="利基/产品关键词")
    country: str = Field("US", description="站点国家代码")
    budget_usd: int = Field(5000, gt=0, description="入市预算（美元）")


class ProductOutput(BaseModel):
    niche_keyword: str
    verdict: str = Field(..., description="强烈推荐 / 推荐 / 谨慎进入 / 不推荐")
    opportunity_score: float
    reasons: list[str]
    recommended_positioning: str
