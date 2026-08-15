"""P1-3 Alembic 迁移守护测试。

不依赖真实 PostgreSQL 实例，用空 SQLite 库验证：
- Alembic 产物（alembic.ini / env.py / 初始迁移）齐全；
- ``alembic upgrade head`` 在空库跑通，生成全部 8 张业务表；
- growth_products 含被原 ``_migrate()`` 硬编码的 category / platform 列；
- 重复执行幂等（已是最新版本则直接返回，不报错）；
- ``app.main`` 仍可导入（无残留的 init_db / engine 引用）。
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
EXPECTED_TABLES = {
    "research_tasks",
    "product_opportunities",
    "growth_products",
    "stage_artifacts",
    "raw_fetches",
    "products",
    "reviews",
    "keyword_metrics",
    "ad_metrics",
    "image_assets",
}


def _sqlite_url(tmp_path: Path) -> str:
    # sqlite:/// + 绝对路径（正斜杠），避免 Windows 反斜杠转义问题
    return "sqlite:///" + str(tmp_path / "mig.db").replace("\\", "/")


def test_alembic_artifacts_present():
    assert (BACKEND_DIR / "alembic.ini").exists(), "缺少 alembic.ini"
    assert (BACKEND_DIR / "migrations" / "env.py").exists(), "缺少 migrations/env.py"
    versions = list((BACKEND_DIR / "migrations" / "versions").glob("*.py"))
    assert versions, "缺少初始迁移版本文件"


def test_migration_creates_all_tables_on_empty_db(monkeypatch, tmp_path):
    from app.migrations_run import run_migrations

    db_url = _sqlite_url(tmp_path)
    monkeypatch.setenv("DATABASE_URL", db_url)
    run_migrations()

    db_file = tmp_path / "mig.db"
    assert db_file.exists()
    with sqlite3.connect(str(db_file)) as conn:
        tables = {r[0] for r in conn.execute(
            "select name from sqlite_master where type='table'"
        )}
    assert EXPECTED_TABLES <= tables, f"缺失表：{EXPECTED_TABLES - tables}"

    with sqlite3.connect(str(db_file)) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(growth_products)")}
    assert "category" in cols and "platform" in cols, "growth_products 缺少 category/platform 列"


def test_migration_is_idempotent(monkeypatch, tmp_path):
    from app.migrations_run import run_migrations

    monkeypatch.setenv("DATABASE_URL", _sqlite_url(tmp_path))
    run_migrations()  # 首次：建表
    run_migrations()  # 二次：已是最新版本，应直接返回不报错


def test_app_imports_without_stale_db_refs():
    """app.main 导入不依赖被删除的 init_db / engine 名称。"""
    from app.main import app  # noqa: F401

    assert app is not None
