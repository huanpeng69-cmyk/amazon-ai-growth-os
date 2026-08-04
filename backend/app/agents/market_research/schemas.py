"""Market Research Agent —— 输入/输出 Schema。

设计要点：输入为国家 + 类目 + 关键词；输出为**经过 AI 分析的市场报告**，
绝不返回原始抓取数据。报告包含 6 个必备板块：市场规模判断 / 竞品数量 /
价格区间 / 头部产品 / 机会点 / 进入建议。
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MarketResearchInput(BaseModel):
    country: str = Field("US", description="Amazon 站点国家代码，如 US / DE / JP")
    category: str = Field(..., description="市场类目，如 Pets / Kitchen / Electronics")
    keyword: str = Field("", description="细分关键词（与类目互补，用于检索更精准的市场）")
    limit: int = Field(20, ge=1, le=50, description="抓取商品样本量，用于统计推断")


class MarketSizeJudgment(BaseModel):
    tier: str = Field(..., description="规模档位：大 / 中 / 小")
    monthly_usd_estimate: Optional[int] = Field(None, description="月规模估算（美元，区间中值）")
    rationale: str = Field(..., description="判断依据（来自清洗后的指标，非原始数据）")


class PriceRange(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None
    currency: str = "USD"
    note: str = Field(..., description="AI 对典型价格带的分析描述")


class TopProductSummary(BaseModel):
    product_name: str
    price: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    why_top: str = Field(..., description="AI 分析其成为头部的原因（洞察，非字段罗列）")


class OpportunityPoint(BaseModel):
    title: str
    detail: str
    evidence: str = Field(..., description="来自清洗后指标的客观依据")


class MarketResearchReport(BaseModel):
    country: str
    category: str
    keyword: str
    market_size: MarketSizeJudgment
    competitor_count: int = Field(..., description="竞品（样本商品）数量，作为竞争烈度代理指标")
    price_range: PriceRange
    top_products: List[TopProductSummary] = Field(..., description="3-5 个头部产品洞察")
    opportunities: List[OpportunityPoint] = Field(..., description="市场机会点")
    entry_recommendation: str = Field(..., description="进入建议（综合结论）")
    summary: str = Field(..., description="执行摘要（AI 综合，1-3 句）")
    generated_by: str = "ai"
    data_source: str = "brightdata"
