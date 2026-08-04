"""数据层 ORM 表。

落库策略：
- raw_fetches      ：缓存各 Connector 的原始响应（避免重复拉取，可追溯）。
- products         ：amazon_connector 的商品快照。
- reviews          ：review_connector 的评论（VOC 原料）。
- keyword_metrics  ：keyword_connector 的关键词指标。
- ad_metrics       ：ads_connector 的广告指标。
- image_assets     ：image_connector 的图片资产。

复用 app.database.Base；由 app/models.py 导入本模块完成注册。
"""
from __future__ import annotations

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
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now()


class RawFetch(Base):
    __tablename__ = "raw_fetches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector: Mapped[str] = mapped_column(String(32), index=True)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(16), default="fixture")  # fixture | live
    payload: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductRecord(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asin: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    country: Mapped[str] = mapped_column(String(8), index=True)
    title: Mapped[str] = mapped_column(String(400), default="")
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bsr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    est_monthly_sales: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sellers: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="fixture")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewRecord(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asin: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    country: Mapped[str] = mapped_column(String(8), index=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    body: Mapped[str] = mapped_column(String(4000), default="")
    is_vp: Mapped[bool] = mapped_column(default=False)
    reviewed_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    pain_keywords: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(16), default="fixture")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KeywordRecord(Base):
    __tablename__ = "keyword_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seed_keyword: Mapped[str] = mapped_column(String(200), index=True)
    country: Mapped[str] = mapped_column(String(8), index=True)
    keyword: Mapped[str] = mapped_column(String(200), default="")
    search_volume: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    competition: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trend: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="fixture")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdRecord(Base):
    __tablename__ = "ad_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asin: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    country: Mapped[str] = mapped_column(String(8), index=True)
    acos: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roas: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ctr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cvr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spend: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ad_sales: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    orders: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    period_start: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    period_end: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="fixture")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImageRecord(Base):
    __tablename__ = "image_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default="reference")  # product|competitor|reference
    asin: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    url: Mapped[str] = mapped_column(String(1000), default="")
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
