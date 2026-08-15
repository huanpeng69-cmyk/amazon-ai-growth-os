"""数据库引擎、会话与 Base。

演示用 SQLite；生产用 PostgreSQL。schema 演进由 Alembic 托管
（见 backend/alembic.ini 与 backend/migrations/），应用启动时执行
``alembic upgrade head``（app/migrations_run.py）。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def init_db() -> None:
    """遗留自举建表（仅演示/脚本用）。

    生产路径请走 Alembic：``run_migrations()`` 对空库执行 ``upgrade head``。
    这里保留以便本地一次性脚本 / 测试在无需 Alembic 时也能建表。
    """
    from . import models  # noqa: F401  确保模型已注册到 Base.metadata

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依赖：请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
