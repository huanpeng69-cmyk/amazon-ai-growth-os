"""Advertising Analysis Agent —— 输入/输出 Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AdvertisingInput(BaseModel):
    product_name: str = Field(..., description="产品名称")
    niche_keyword: str = Field("", description="利基/核心词")
    product_id: Optional[str] = Field(None, description="产品空间 ID，用于自动预填与回写")
    country: str = Field("US", description="站点国家代码")
    budget_usd: int = Field(0, description="月广告预算（0 表示未知，仅给比例建议）")
    current_acos: Optional[float] = Field(None, description="当前 ACOS（可选，用于对比）")


class AdMetric(BaseModel):
    key: str
    value: str
    delta: str
    trend: str = Field("flat", description="up / down / flat")


class CampaignAction(BaseModel):
    campaign_type: str = Field(..., description="SP / SB / SD")
    match_type: str = Field(..., description="exact / phrase / broad")
    action: str = Field(..., description="加预算 / 否词 / 暂停 / 新建 / 迁移")
    target: str = Field(..., description="关键词或广告组")
    rationale: str


class AdvertisingOutput(BaseModel):
    product_name: str
    country: str
    summary: str
    metrics: List[AdMetric]
    campaign_actions: List[CampaignAction]
    budget_recommendation: str
    efficiency_score: float = Field(..., description="广告效率 0-100（供生命周期评分）")
