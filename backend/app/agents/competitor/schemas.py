"""Competitor Agent —— 输入/输出 Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CompetitorInput(BaseModel):
    niche_keyword: str = Field(..., description="利基/产品关键词，如 'wireless earbuds'")
    country: str = Field("US", description="站点国家代码")
    top_n: int = Field(5, ge=1, le=10, description="返回竞品数量")
    product_id: Optional[str] = Field(None, description="产品空间 ID，用于自动预填与回写")


class CompetitorProfile(BaseModel):
    name: str
    price_usd: float
    avg_reviews: int
    rating: float
    est_market_share: float = Field(..., description="估计市场份额 0-1")
    weakness: str


class CompetitorOutput(BaseModel):
    niche_keyword: str
    country: str
    competitors: List[CompetitorProfile]
    summary: str
