"""market_search 工具 —— 输入/输出 JSON 契约。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MarketSignal(BaseModel):
    niche_id: str
    product_name: str
    niche_keyword: str
    search_volume_monthly: int
    avg_price_usd: float
    num_sellers: int
    avg_reviews: int
    top_seller_share: float
    growth_yoy: float
    pain_points: list[dict[str, Any]]  # 原始痛点：{pain, base_severity, evidence}


class MarketSearchInput(BaseModel):
    country: str = Field(..., description="Amazon 站点国家代码")
    category: str = Field(..., description="Amazon 类目或利基关键词")
    pool_size: int = Field(24, description="候选利基数量", ge=1, le=100)


class MarketSearchOutput(BaseModel):
    country: str
    category: str
    signals: list[MarketSignal]
