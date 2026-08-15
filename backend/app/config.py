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

# Agent（外部 IO：Agnes / Bright Data）整体处理超时（秒）。
# 超过则请求被熔断返回 504（降级），避免长调用占死 worker / 客户端悬挂。
AGENT_TIMEOUT_SECONDS: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "120"))
# 全局请求超时（秒），作为兜底护栏（默认 5 分钟）。
REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "300"))

# 市场调研结果缓存 TTL（秒）与容量；相同 country+category+keyword+limit 命中缓存，
# 避免重复打 Bright Data + LLM（慢且贵）。TTL=0 关闭缓存。
RESEARCH_CACHE_TTL_SECONDS: int = int(os.getenv("RESEARCH_CACHE_TTL_SECONDS", "600"))
RESEARCH_CACHE_MAXSIZE: int = int(os.getenv("RESEARCH_CACHE_MAXSIZE", "256"))

# 生成候选利基的市场信号数量（评分后取前 10）
CANDIDATE_POOL_SIZE: int = 24
TOP_N: int = 10
