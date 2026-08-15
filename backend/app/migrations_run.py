"""在应用启动时以编程方式执行 Alembic 迁移（替代手写 ``_migrate()``）。

由 ``app.main`` 的 lifespan 调用，读取与 ORM 相同的 ``DATABASE_URL``，
对空库执行 ``alembic upgrade head`` 完成建表。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("aigos.migrations")


def run_migrations() -> None:
    """对当前 DATABASE_URL 执行 ``alembic upgrade head``。

    - 幂等：已应用最新版本时 Alembic 直接返回，不会重复建表。
    - 失败向上抛出，由 lifespan 终止启动，避免带着缺表的服务跑起来。
    """
    from alembic import command
    from alembic.config import Config

    # alembic.ini 位于 backend/（本文件在 backend/app/）
    ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    if not ini_path.exists():
        raise FileNotFoundError(f"找不到 Alembic 配置：{ini_path}")

    cfg = Config(str(ini_path))
    # 优先用环境变量；否则回落到 app.config.DATABASE_URL（绝对路径，
    # 与 database.engine 用的是同一份配置，避免 CWD 相对路径错位）。
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        from app.config import DATABASE_URL as _cfg_url

        db_url = _cfg_url
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)

    logger.info("运行数据库迁移 alembic upgrade head (url=%s)", _mask(db_url or ""))
    command.upgrade(cfg, "head")
    logger.info("数据库迁移完成")


def _mask(url: str) -> str:
    """遮蔽连接串中的密码，避免写进日志。"""
    if "://" not in url:
        return url
    try:
        head, _, rest = url.partition("@")
        scheme, _, creds = head.partition("://")
        if ":" in creds:
            user, _, _pw = creds.partition(":")
            return f"{scheme}://{user}:***@" + rest
        return f"{scheme}://{creds}@" + rest
    except Exception:
        return "***"
