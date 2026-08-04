"""image_generation 工具 —— 输入/输出 JSON 契约（电商详情页图片方案）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GeneratedImage(BaseModel):
    scene: str
    aspect_ratio: str
    prompt: str
    description: str
    image_url: Optional[str] = Field(None, description="AI 生成的真实图片 URL（WisArt 返回）")


class ImageGenInput(BaseModel):
    product_name: str = Field(..., description="产品名称")
    niche_keyword: str = Field(..., description="利基关键词（用于风格/卖点定位）")
    style: str = Field("ecommerce", description="图片风格，如 ecommerce / lifestyle / minimal")
    count: int = Field(4, description="生成图片数量", ge=1, le=8)
    platform: str = Field("amazon", description="目标平台，如 amazon / shopify")
    prompts: list[str] = Field(
        default_factory=list,
        description="每张图要用的文生图 Prompt（与 count 对齐）。提供后生图即用这些 Prompt，"
                    "保证『展示的 Prompt』=『真实生图 Prompt』，且每张差异化。",
    )


class ImageGenOutput(BaseModel):
    product_name: str
    platform: str
    images: list[GeneratedImage]
