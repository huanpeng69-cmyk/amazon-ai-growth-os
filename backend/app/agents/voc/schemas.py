"""VOC Agent —— 输入/输出 Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class VOCInput(BaseModel):
    product_name: str = Field(..., description="产品/利基名称")
    country: str = Field("US", description="站点国家代码")
    product_id: Optional[str] = Field(None, description="产品空间 ID，用于自动预填与回写")


class PainPointOut(BaseModel):
    pain: str
    severity: float = Field(..., ge=0, le=100)
    evidence: int
    suggested_fix: str


class VOCOutput(BaseModel):
    product_name: str
    country: str
    pain_points: List[PainPointOut]
    strengths: List[str]
    summary: str
