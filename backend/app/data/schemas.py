"""领域模型（Data Processing 的输出、Agent 的输入）。

这些是「结构化后的真实数据」，由 data/processing/parse_*.py 从 RawData.payload 解析得到，
经 DAL 落库后供 Agent 直接消费。Agent 不接触原始 API 结构。
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ProductData(BaseModel):
    asin: Optional[str] = None
    country: str = "US"
    title: str = ""
    price: Optional[float] = None
    bsr: Optional[int] = None
    est_monthly_sales: Optional[int] = None
    sellers: Optional[int] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    category: Optional[str] = None


class ReviewItem(BaseModel):
    rating: float = 0.0
    body: str = ""
    is_vp: bool = False
    reviewed_at: Optional[str] = None
    pain_keywords: List[str] = Field(default_factory=list)


class KeywordData(BaseModel):
    keyword: str = ""
    search_volume: Optional[int] = None
    competition: Optional[float] = None   # 0-100
    cpc: Optional[float] = None
    trend: Optional[str] = None           # up / flat / down


class AdData(BaseModel):
    acos: Optional[float] = None
    roas: Optional[float] = None
    ctr: Optional[float] = None
    cvr: Optional[float] = None
    spend: Optional[float] = None
    ad_sales: Optional[float] = None
    orders: Optional[int] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None


class ImageData(BaseModel):
    url: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    kind: str = "reference"               # product | competitor | reference
    source: str = ""


class MarketSignal(BaseModel):
    """蓝海挖掘的市场聚合信号（由 amazon + keyword + review 组合而来）。"""

    country: str = "US"
    category: Optional[str] = None
    niche_keyword: str = ""
    product_name: str = ""
    search_volume_monthly: Optional[int] = None
    avg_price_usd: Optional[float] = None
    num_sellers: Optional[int] = None
    avg_reviews: Optional[int] = None
    top_seller_share: Optional[float] = None
    growth_yoy: Optional[float] = None
    pain_points: List[dict] = Field(default_factory=list)
