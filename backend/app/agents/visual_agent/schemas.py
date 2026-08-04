"""Product Visual Agent —— 输入/输出 Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class VisualAgentInput(BaseModel):
    product_name: str = Field(..., description="产品名称")
    niche_keyword: str = Field("", description="核心利基/场景关键词")
    product_id: Optional[str] = Field(None, description="产品空间 ID，用于自动预填与回写")
    market_positioning: str = Field("", description="市场定位（一句话）")
    voc_pain_points: List[str] = Field(default_factory=list, description="VOC 痛点列表")
    competitor_insights: str = Field("", description="竞品分析（文本，含软肋/格局）")
    style: str = Field("ecommerce", description="风格 ecommerce / lifestyle / minimal / premium_clean / luxury / playful")
    country: str = Field("US", description="站点国家代码")

    # 新增字段（前端左右分栏版）
    website: str = Field("", description="商品网站/品牌站 URL")
    platform: str = Field("amazon", description="平台 amazon / shopify / independent")
    target_audience: str = Field("", description="目标人群描述")
    selling_points: str = Field("", description="核心卖点（逗号分隔）")
    extra_requirements: str = Field("", description="补充需求说明")
    image_count: int = Field(6, ge=1, le=12, description="生成图片数量")
    batch_reference_mode: bool = Field(False, description="是否启用一键批量参考图模式")


class VisualStrategy(BaseModel):
    main_image_strategy: str = Field(..., description="主图策略")
    visual_angles: List[str] = Field(default_factory=list, description="视觉角度")
    differentiation: str = Field(..., description="差异化锚点（呼应竞品）")
    emotional_hook: str = Field(..., description="情感钩子")
    color_direction: str = Field(..., description="色彩方向")


class ImageSlot(BaseModel):
    slot: str = Field(..., description="主图 / 附图1..附图6")
    purpose: str = Field(..., description="主图白底 / 卖点特写 / 使用场景 / 痛点对比 / 尺寸规格 / 生活方式 / 信任背书")
    concept: str = Field(..., description="创意概念")
    differentiation_point: str = Field(..., description="差异化要点")
    pain_addressed: Optional[str] = Field(None, description="呼应的 VOC 痛点")
    aspect_ratio: str = Field("1:1")
    generation_prompt: str = Field(..., description="文生图 Prompt")
    quality_checks: List[str] = Field(default_factory=list, description="该图质量检查点")
    generation_request: dict = Field(default_factory=dict, description="调用 image_generation 工具的请求 JSON")
    generated_scene: str = Field("", description="工具返回的场景（生成结果）")
    generated_description: str = Field("", description="工具返回的描述（生成结果）")
    image_url: Optional[str] = Field(None, description="AI 生成的真实图片 URL（Agnes/WisArt 返回）")


class VisualAgentOutput(BaseModel):
    product_name: str
    strategy: VisualStrategy
    image_plan: List[ImageSlot] = Field(..., description="7 张 Listing 图片规划")
    quality_score: float = Field(..., description="视觉质量评分 0-100")
    optimization_suggestions: List[str] = Field(default_factory=list)
    composition_strategy: str = Field(..., description="整体构图策略")
