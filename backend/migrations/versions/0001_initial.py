"""initial schema — 全部 ORM 表（蓝海挖掘 / 生命周期 / 数据层）

从手写 ``_migrate()`` （仅 2 个 ALTER）迁移到 Alembic 托管的权威 schema。
覆盖 8 张表：research_tasks / product_opportunities / growth_products /
stage_artifacts / raw_fetches / products / reviews / keyword_metrics /
ad_metrics / image_assets。

双后端兼容：
- SQLite：JSON 落 TEXT、CURRENT_TIMESTAMP 作 server_default；
- PostgreSQL：JSON 落 JSON、TIMESTAMPTZ 作 server_default。
两者均无需在迁移中写后端专有语法。

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("CURRENT_TIMESTAMP")  # SQLite / PostgreSQL 通用


def upgrade() -> None:
    op.create_table(
        "research_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("country", sa.String(8), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("budget_usd", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("task_id", name="uq_research_tasks_task_id"),
    )
    op.create_index("ix_research_tasks_country", "research_tasks", ["country"])
    op.create_index("ix_research_tasks_category", "research_tasks", ["category"])

    op.create_table(
        "product_opportunities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id_fk", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("niche_keyword", sa.String(200), nullable=False),
        sa.Column("market_size_monthly_usd", sa.Integer(), nullable=False),
        sa.Column("market_size_growth_yoy", sa.Float(), nullable=False),
        sa.Column("competition_level", sa.String(16), nullable=False),
        sa.Column("competition_score", sa.Float(), nullable=False),
        sa.Column("top_pain_points", sa.JSON(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("entry_recommendation", sa.String(2000), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("pain_severity_score", sa.Float(), nullable=False),
        sa.Column("budget_fit_score", sa.Float(), nullable=False),
        sa.Column("source_signals", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id_fk"], ["research_tasks.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_product_opportunities_task_id_fk", "product_opportunities", ["task_id_fk"])

    op.create_table(
        "growth_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("niche_keyword", sa.String(200), server_default="", nullable=False),
        sa.Column("category", sa.String(80), server_default="", nullable=False),
        sa.Column("country", sa.String(8), server_default="US", nullable=False),
        sa.Column("platform", sa.String(20), server_default="amazon", nullable=False),
        sa.Column("budget_usd", sa.Integer(), server_default="5000", nullable=False),
        sa.Column("current_stage", sa.String(16), server_default="discover", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_TS,
            onupdate=_TS,
            nullable=False,
        ),
        sa.UniqueConstraint("product_id", name="uq_growth_products_product_id"),
    )

    op.create_table(
        "stage_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_fk", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(16), server_default="", nullable=False),
        sa.Column("status", sa.String(16), server_default="done", nullable=False),
        sa.Column("score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("summary", sa.String(2000), server_default="", nullable=False),
        sa.Column("data", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["product_fk"], ["growth_products.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_stage_artifacts_product_fk", "stage_artifacts", ["product_fk"])
    op.create_index("ix_stage_artifacts_stage", "stage_artifacts", ["stage"])

    op.create_table(
        "raw_fetches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connector", sa.String(32), server_default="", nullable=False),
        sa.Column("query_hash", sa.String(64), server_default="", nullable=False),
        sa.Column("source", sa.String(16), server_default="fixture", nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
    )
    op.create_index("ix_raw_fetches_connector", "raw_fetches", ["connector"])
    op.create_index("ix_raw_fetches_query_hash", "raw_fetches", ["query_hash"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asin", sa.String(32), nullable=True),
        sa.Column("country", sa.String(8), server_default="", nullable=False),
        sa.Column("title", sa.String(400), server_default="", nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("bsr", sa.Integer(), nullable=True),
        sa.Column("est_monthly_sales", sa.Integer(), nullable=True),
        sa.Column("sellers", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("source", sa.String(16), server_default="fixture", nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
    )
    op.create_index("ix_products_asin", "products", ["asin"])
    op.create_index("ix_products_country", "products", ["country"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asin", sa.String(32), nullable=True),
        sa.Column("country", sa.String(8), server_default="", nullable=False),
        sa.Column("rating", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("body", sa.String(4000), server_default="", nullable=False),
        sa.Column("is_vp", sa.Boolean(), default=False),
        sa.Column("reviewed_at", sa.String(32), nullable=True),
        sa.Column("pain_keywords", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("source", sa.String(16), server_default="fixture", nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
    )
    op.create_index("ix_reviews_asin", "reviews", ["asin"])
    op.create_index("ix_reviews_country", "reviews", ["country"])

    op.create_table(
        "keyword_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seed_keyword", sa.String(200), server_default="", nullable=False),
        sa.Column("country", sa.String(8), server_default="", nullable=False),
        sa.Column("keyword", sa.String(200), server_default="", nullable=False),
        sa.Column("search_volume", sa.Integer(), nullable=True),
        sa.Column("competition", sa.Float(), nullable=True),
        sa.Column("cpc", sa.Float(), nullable=True),
        sa.Column("trend", sa.String(16), nullable=True),
        sa.Column("source", sa.String(16), server_default="fixture", nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
    )
    op.create_index("ix_keyword_metrics_seed_keyword", "keyword_metrics", ["seed_keyword"])
    op.create_index("ix_keyword_metrics_country", "keyword_metrics", ["country"])

    op.create_table(
        "ad_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asin", sa.String(32), nullable=True),
        sa.Column("country", sa.String(8), server_default="", nullable=False),
        sa.Column("acos", sa.Float(), nullable=True),
        sa.Column("roas", sa.Float(), nullable=True),
        sa.Column("ctr", sa.Float(), nullable=True),
        sa.Column("cvr", sa.Float(), nullable=True),
        sa.Column("spend", sa.Float(), nullable=True),
        sa.Column("ad_sales", sa.Float(), nullable=True),
        sa.Column("orders", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.String(32), nullable=True),
        sa.Column("period_end", sa.String(32), nullable=True),
        sa.Column("source", sa.String(16), server_default="fixture", nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
    )
    op.create_index("ix_ad_metrics_asin", "ad_metrics", ["asin"])
    op.create_index("ix_ad_metrics_country", "ad_metrics", ["country"])

    op.create_table(
        "image_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(16), server_default="reference", nullable=False),
        sa.Column("asin", sa.String(32), nullable=True),
        sa.Column("url", sa.String(1000), server_default="", nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(64), server_default="", nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
    )
    op.create_index("ix_image_assets_asin", "image_assets", ["asin"])


def downgrade() -> None:
    op.drop_table("image_assets")
    op.drop_table("ad_metrics")
    op.drop_table("keyword_metrics")
    op.drop_table("reviews")
    op.drop_table("products")
    op.drop_table("raw_fetches")
    op.drop_table("stage_artifacts")
    op.drop_table("growth_products")
    op.drop_table("product_opportunities")
    op.drop_table("research_tasks")
