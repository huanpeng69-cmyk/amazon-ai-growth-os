"""数据库引擎、会话与 Base。

演示用 SQLite；生产用 PostgreSQL（见 db/schema.sql）。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def init_db() -> None:
    """创建所有表（演示环境用 ORM 自举；生产用 db/schema.sql 迁移）。"""
    from . import models  # noqa: F401  确保模型已注册到 Base.metadata

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依赖：请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
