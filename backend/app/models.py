"""ORM 模型 —— 蓝海市场挖掘。

两张核心表：
- research_tasks         一次「国家 + 类目 + 预算」的挖掘任务
- product_opportunities  任务产出的潜力产品（Top 10）
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    country: Mapped[str] = mapped_column(String(8), index=True)          # US / DE / JP ...
    category: Mapped[str] = mapped_column(String(120), index=True)       # 类目
    budget_usd: Mapped[int] = mapped_column(Integer)                     # 入市预算（美元）
    status: Mapped[str] = mapped_column(String(16), default="pending")   # pending/running/done/failed
    error: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    opportunities: Mapped[list["ProductOpportunity"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="ProductOpportunity.rank"
    )


class ProductOpportunity(Base):
    __tablename__ = "product_opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id_fk: Mapped[int] = mapped_column(ForeignKey("research_tasks.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)                                  # 1..10

    product_name: Mapped[str] = mapped_column(String(200))
    niche_keyword: Mapped[str] = mapped_column(String(200))                     # 利基长尾词

    # —— 用户要求的核心字段 ——
    market_size_monthly_usd: Mapped[int] = mapped_column(Integer)              # 市场规模（月营收估算）
    market_size_growth_yoy: Mapped[float] = mapped_column(Float)               # 同比增速
    competition_level: Mapped[str] = mapped_column(String(16))                 # Low / Medium / High
    competition_score: Mapped[float] = mapped_column(Float)                    # 0-100（越高越蓝海）
    top_pain_points: Mapped[list] = mapped_column(JSON)                        # [{pain, severity, evidence}]
    opportunity_score: Mapped[float] = mapped_column(Float)                    # 0-100
    entry_recommendation: Mapped[str] = mapped_column(String(2000))            # 进入建议

    # —— 可解释性辅助分 ——
    demand_score: Mapped[float] = mapped_column(Float)
    pain_severity_score: Mapped[float] = mapped_column(Float)
    budget_fit_score: Mapped[float] = mapped_column(Float)
    source_signals: Mapped[dict] = mapped_column(JSON)                         # 原始市场信号（可追溯）

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["ResearchTask"] = relationship(back_populates="opportunities")


# 注册生命周期表（在 Base.metadata 上建表）
from .lifecycle import models as _lifecycle_models  # noqa: E402,F401

# 注册统一数据层表（Connector / Processing / DB：raw_fetches / products / reviews / ...）
from .data import models as _data_models  # noqa: E402,F401
