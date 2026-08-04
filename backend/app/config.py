"""全局配置。

演示默认使用 SQLite（无需独立数据库服务即可运行）；
生产环境通过环境变量 DATABASE_URL 切换为 PostgreSQL + pgvector。
"""
import os
from pathlib import Path

# backend/ 目录（config.py 位于 backend/app/）
BACKEND_DIR = Path(__file__).resolve().parent.parent
# 项目根目录 amazon-ai-growth-os/
ROOT_DIR = BACKEND_DIR.parent

DEFAULT_DB_URL = f"sqlite:///{BACKEND_DIR / 'amazon_growth_os.db'}"

DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_DB_URL)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
APP_ENV: str = os.getenv("APP_ENV", "demo")

# 生成候选利基的市场信号数量（评分后取前 10）
CANDIDATE_POOL_SIZE: int = 24
TOP_N: int = 10
