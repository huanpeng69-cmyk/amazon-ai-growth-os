"""Image Generation Agent —— 输入/输出 Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ImageGenAgentInput(BaseModel):
    product_name: str = Field(..., description="产品名称")
    niche_keyword: str = Field("", description="利基/场景关键词")
    product_id: Optional[str] = Field(None, description="产品空间 ID，用于自动预填与回写")
    style: str = Field("ecommerce", description="风格 ecommerce / lifestyle / minimal")
    count: int = Field(6, ge=1, le=8, description="生成图片数量")
    platform: str = Field("amazon", description="目标平台 amazon / shopify")


class ImageShotPlan(BaseModel):
    scene: str
    aspect_ratio: str
    prompt: str
    description: str
    purpose: str = Field(..., description="用途：主图/场景/卖点/对比/规格/生活方式")
    priority: int = Field(..., description="拍摄/生成优先级 1 最高")


class ImageGenAgentOutput(BaseModel):
    product_name: str
    platform: str
    shots: List[ImageShotPlan]
    composition_strategy: str
    brand_guidance: str
    readiness_score: float = Field(..., description="视觉完整度 0-100（供生命周期评分）")
