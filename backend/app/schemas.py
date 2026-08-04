"""Pydantic 请求/响应模型。

蓝海挖掘 API 的对外契约。
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BlueOceanRequest(BaseModel):
    """用户输入：国家 + 类目 + 预算。"""
    country: str = Field(..., min_length=2, max_length=8, example="US", description="站点国家代码 US/DE/JP/UK ...")
    category: str = Field(..., min_length=1, max_length=120, example="Kitchen", description="Amazon 类目")
    budget_usd: int = Field(..., gt=0, example=5000, description="入市预算（美元）")
    product_id: Optional[str] = Field(None, description="产品空间 ID，用于把蓝海机会回写供联动复用")


class PainPoint(BaseModel):
    pain: str
    severity: float = Field(..., ge=0, le=100, description="痛点严重度 0-100")
    evidence: int = Field(..., ge=0, description="评论中提及次数（VOC 证据量）")


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

    top_pain_points: List[PainPoint]
    opportunity_score: float
    entry_recommendation: str


class BlueOceanResult(BaseModel):
    task_id: str
    country: str
    category: str
    budget_usd: int
    status: str
    products: List[ProductOpportunityOut]
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
