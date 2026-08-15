"""Alembic 环境 —— 同时支持 SQLite（本地/演示）与 PostgreSQL（生产）。

- 导入 ``app.database.Base`` 作为 ``target_metadata``（自动覆盖全部 ORM 表）。
- 优先读取环境变量 ``DATABASE_URL`` 覆盖 alembic.ini 中的默认连接。
- SQLite 下开启 ``render_as_batch``，使后续 ALTER/DROP 列迁移可在 SQLite 生效。
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# 把 backend/ 目录加入 sys.path，确保 `from app...` 在任何工作目录都能导入。
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 必须在导入模型之前确保 DATABASE_URL 已生效（config.py 在导入时读取一次）。
from app.database import Base  # noqa: E402
from app import models  # noqa: F401,E402  确保全部 ORM 表注册到 Base.metadata

config = context.config

# 生产 / 自定义连接：用环境变量 DATABASE_URL 覆盖 ini 默认值。
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        # 无日志配置时静默继续（如某些精简环境）
        pass

target_metadata = Base.metadata


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL，不连接数据库。"""
    url = config.get_main_option("sqlalchemy.url") or ""
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=_is_sqlite(url),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库并执行迁移。"""
    url = config.get_main_option("sqlalchemy.url") or ""
    section = config.get_section(config.config_ini_section, {})
    connect_args = {"check_same_thread": False} if _is_sqlite(url) else {}
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=_is_sqlite(url),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
