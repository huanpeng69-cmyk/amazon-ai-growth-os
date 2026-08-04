"""Lifecycle ORM 模型。

- growth_products   一个被增长操作系统接管的产品（含当前阶段）
- stage_artifacts   产品在某一阶段产出的制品（评分 + 结构化数据）
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class GrowthProduct(Base):
    __tablename__ = "growth_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    niche_keyword: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(80), default="")
    country: Mapped[str] = mapped_column(String(8), default="US")
    platform: Mapped[str] = mapped_column(String(20), default="amazon")
    budget_usd: Mapped[int] = mapped_column(Integer, default=5000)
    current_stage: Mapped[str] = mapped_column(String(16), default="discover")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())

    artifacts: Mapped[list["StageArtifact"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="StageArtifact.id"
    )


class StageArtifact(Base):
    __tablename__ = "stage_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_fk: Mapped[int] = mapped_column(ForeignKey("growth_products.id"), index=True)
    stage: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="done")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str] = mapped_column(String(2000), default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped["GrowthProduct"] = relationship(back_populates="artifacts")
