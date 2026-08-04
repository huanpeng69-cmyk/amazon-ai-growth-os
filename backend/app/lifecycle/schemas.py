"""Lifecycle Pydantic 契约。"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StageInfo(BaseModel):
    stage: str
    label: str
    status: str = Field(..., description="done / current / locked")
    score: Optional[float] = None
    summary: str = ""


class GrowthProductOut(BaseModel):
    product_id: str
    name: str
    niche_keyword: str
    category: str = ""
    country: str
    platform: str = "amazon"
    budget_usd: int
    current_stage: str
    overall_health: float
    stages: List[StageInfo]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreateProductRequest(BaseModel):
    name: str = Field(..., description="产品名称")
    niche_keyword: str = Field("", description="核心利基/场景关键词")
    category: str = Field("", description="类目/品类")
    country: str = Field("US", description="站点国家代码")
    platform: str = Field("amazon", description="平台 amazon / shopify / independent")
    budget_usd: int = Field(5000, gt=0, description="入市/广告预算（美元）")
