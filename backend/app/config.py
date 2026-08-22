"""全局配置 —— 经 pydantic-settings 校验。

设计要点：
1. 类型校验：所有数值字段带范围约束（ge/le），非法值（如 AGENT_TIMEOUT_SECONDS=abc、
   或负数）在 ``Settings()`` 实例化时即抛 ``ValidationError`` → 模块导入失败 → 服务无法
   启动（fail-fast），而非带着错误配置静默运行。
2. 环境覆盖：pydantic-settings 默认读取真实进程环境变量（12-factor）；.env 由
   ``app.config_store`` 在启动时注入 os.environ，这里不再重复读取 .env 文件。
3. 向后兼容：保留模块级常量（``DATABASE_URL`` / ``APP_ENV`` 等），既有
   ``from app.config import X`` 调用方无需改动。

演示默认使用 SQLite（无需独立数据库服务即可运行）；
生产环境通过环境变量 DATABASE_URL 切换为 PostgreSQL + pgvector。
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录（config.py 位于 backend/app/）
BACKEND_DIR = Path(__file__).resolve().parent.parent
# 项目根目录 amazon-ai-growth-os/
ROOT_DIR = BACKEND_DIR.parent

_DEFAULT_DB_URL = f"sqlite:///{BACKEND_DIR / 'amazon_growth_os.db'}"


class Settings(BaseSettings):
    """服务端配置。导入即实例化（见模块底部 ``settings`` 单例）以达成 fail-fast。"""

    model_config = SettingsConfigDict(
        # 不读 .env 文件：.env 由 config_store 在启动时写入 os.environ，此处只认真实环境。
        env_file=None,
        extra="ignore",
        case_sensitive=False,
    )

    # —— 数据层 ——
    DATABASE_URL: str = Field(default=_DEFAULT_DB_URL)
    OPENAI_API_KEY: str = Field(default="")
    APP_ENV: str = Field(default="demo")  # demo / development / production / test

    # —— 超时护栏（秒）——
    # Agent（外部 IO：Agnes / Bright Data）整体处理超时。超过则熔断返回 504（降级）。
    AGENT_TIMEOUT_SECONDS: int = Field(default=120, ge=1, le=3600)
    # 全局请求超时（兜底护栏，默认 5 分钟）。
    REQUEST_TIMEOUT_SECONDS: int = Field(default=300, ge=1, le=3600)

    # —— 市场调研结果缓存 ——
    # TTL=0 关闭缓存；容量下限 1。
    RESEARCH_CACHE_TTL_SECONDS: int = Field(default=600, ge=0)
    RESEARCH_CACHE_MAXSIZE: int = Field(default=256, ge=1)

    # —— 候选利基规模 ——
    CANDIDATE_POOL_SIZE: int = Field(default=24, ge=1)  # 评分后取前 TOP_N
    TOP_N: int = Field(default=10, ge=1)


# 单例：模块导入即实例化 → 配置非法时启动即失败（fail-fast）。
# 包装为 RuntimeError，错误信息直接指向校验失败字段，便于运维定位。
try:
    settings = Settings()
except ValidationError as e:
    raise RuntimeError(
        "配置校验失败，服务拒绝启动（请检查环境变量）：\n" + str(e)
    ) from e

# ── 向后兼容的模块级常量（既有 from app.config import X 调用方无需改动）──
DATABASE_URL = settings.DATABASE_URL
OPENAI_API_KEY = settings.OPENAI_API_KEY
APP_ENV = settings.APP_ENV
AGENT_TIMEOUT_SECONDS = settings.AGENT_TIMEOUT_SECONDS
REQUEST_TIMEOUT_SECONDS = settings.REQUEST_TIMEOUT_SECONDS
RESEARCH_CACHE_TTL_SECONDS = settings.RESEARCH_CACHE_TTL_SECONDS
RESEARCH_CACHE_MAXSIZE = settings.RESEARCH_CACHE_MAXSIZE
CANDIDATE_POOL_SIZE = settings.CANDIDATE_POOL_SIZE
TOP_N = settings.TOP_N
