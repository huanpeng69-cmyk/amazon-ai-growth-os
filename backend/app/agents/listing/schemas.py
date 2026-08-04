"""Listing Agent —— 输入/输出 Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.tools.image_generation.schemas import GeneratedImage


class ListingInput(BaseModel):
    product_name: str = Field(..., description="产品名称")
    niche_keyword: str = Field("", description="核心利基/场景关键词（用于风格与流量词定位）")
    product_id: Optional[str] = Field(None, description="产品空间 ID，用于自动预填与回写")
    key_features: List[str] = Field(default_factory=list, description="核心卖点（2-5 个）")
    tone: str = Field("专业可信", description="语气：专业可信 / 年轻活力 / 高端奢华")
    target_country: str = Field("US", description="目标站点国家代码（欧美主要国家）")
    language: str = Field("en", description="面向买家的 Listing 输出语言，默认 en（全英文，适配欧美站点）")


class ListingOutput(BaseModel):
    product_name: str
    tone: str
    title: str
    bullet_points: List[str]
    description: str
    search_terms: List[str]
    image_plan: List[GeneratedImage] = Field(default_factory=list, description="主图到附图的生成方案")
    compliance_notes: List[str] = Field(default_factory=list, description="合规与优化提示")
    completeness_score: float = Field(..., description="Listing 完整度 0-100（供生命周期评分）")
