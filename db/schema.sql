-- ============================================================
-- Amazon AI Growth OS —— 生产数据库 DDL（PostgreSQL 16 + pgvector）
-- 蓝海市场挖掘模块
-- 用法： psql "$DATABASE_URL" -f db/schema.sql
--
-- ⚠️ 弃用说明（2026-08-15）：本文件已不再是 schema 演进的权威来源。
-- 数据库 schema 现由 Alembic 托管（backend/alembic.ini + backend/migrations/），
-- 应用启动时执行 `alembic upgrade head` 建表/演进。本文件仅保留作 PostgreSQL
-- 生产库参考（含 pgvector embedding 列意图），且其中的 task_id 用 UUID、
-- 仅含 research/product 两张表，与当前 ORM 模型（task_id 为 String(36)、
-- 另含 lifecycle/data 多张表）并不一致，请勿直接用于建表。
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- 一次挖掘任务
CREATE TABLE IF NOT EXISTS research_tasks (
    id                  BIGSERIAL PRIMARY KEY,
    task_id             UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    country             VARCHAR(8)  NOT NULL,
    category            VARCHAR(120) NOT NULL,
    budget_usd          INTEGER      NOT NULL,
    status              VARCHAR(16)  NOT NULL DEFAULT 'pending',
    error               TEXT,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_research_tasks_country   ON research_tasks (country);
CREATE INDEX IF NOT EXISTS ix_research_tasks_category  ON research_tasks (category);

-- 任务产出的潜力产品
CREATE TABLE IF NOT EXISTS product_opportunities (
    id                       BIGSERIAL PRIMARY KEY,
    task_id_fk               BIGINT NOT NULL REFERENCES research_tasks (id) ON DELETE CASCADE,
    rank                     INTEGER NOT NULL,

    product_name             VARCHAR(200) NOT NULL,
    niche_keyword            VARCHAR(200) NOT NULL,

    market_size_monthly_usd  INTEGER NOT NULL,
    market_size_growth_yoy   DOUBLE PRECISION NOT NULL,
    competition_level        VARCHAR(16) NOT NULL,
    competition_score        DOUBLE PRECISION NOT NULL,
    top_pain_points          JSONB NOT NULL,
    opportunity_score        DOUBLE PRECISION NOT NULL,
    entry_recommendation     TEXT NOT NULL,

    demand_score             DOUBLE PRECISION NOT NULL,
    pain_severity_score      DOUBLE PRECISION NOT NULL,
    budget_fit_score         DOUBLE PRECISION NOT NULL,
    source_signals           JSONB NOT NULL,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_po_task        ON product_opportunities (task_id_fk);
CREATE INDEX IF NOT EXISTS ix_po_rank        ON product_opportunities (task_id_fk, rank);
-- 向量列：将 source_signals / pain_points 嵌入后可用于相似利基检索（后续扩展）
ALTER TABLE product_opportunities ADD COLUMN IF NOT EXISTS embedding vector(1536);

COMMENT ON TABLE research_tasks IS '蓝海挖掘任务：国家 + 类目 + 预算';
COMMENT ON TABLE product_opportunities IS '每次任务产出的 Top-N 潜力产品';
