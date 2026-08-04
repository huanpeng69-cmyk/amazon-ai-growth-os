"""voc_analysis 工具 —— 输入/输出 JSON 契约（用户评论 VOC 分析）。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class VOCPainPoint(BaseModel):
    pain: str
    severity: float
    evidence: int
    suggested_fix: str


class VOCInput(BaseModel):
    niche_keyword: str = Field(..., description="利基关键词或 ASIN 对应的产品名")
    country: str = Field("US", description="站点国家代码")
    asin: Optional[str] = Field(None, description="可选：指定 ASIN 拉取真实评论")
    top_n: int = Field(5, description="返回 Top-N 痛点", ge=1, le=20)


class VOCOutput(BaseModel):
    niche_keyword: str
    country: str
    pain_points: list[VOCPainPoint]
    summary: str
