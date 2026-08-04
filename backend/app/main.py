"""FastAPI 应用入口。

- 启动建表
- 挂载蓝海挖掘 API
- 在 / 提供单页前端（零构建可演示）
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def _load_env_file() -> None:
    """零依赖读取项目根目录 .env（若存在）。

    必须在导入 routers/Agent 之前调用——Agnes 客户端与后端选择都是
    模块加载时读一次环境变量，晚于此将无法生效。
    """
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


_load_env_file()

from .database import init_db, engine
from .routers import agent as agent_router
from .routers import blue_ocean
from .routers import tools as tools_router
from .routers import lifecycle as lifecycle_router
from .routers import settings as settings_router
from .routers import workspace as workspace_router
from .routers import profit as profit_router
from .routers import data as data_router

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


def _migrate() -> None:
    """兼容已有 SQLite 库：补充 growth_products 的新列（category / platform）。

    create_all 不会给已存在的表加列，故用 ALTER TABLE 兜底。
    """
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(growth_products)")).fetchall()}
            alters = []
            if "category" not in cols:
                alters.append("ALTER TABLE growth_products ADD COLUMN category VARCHAR(80) DEFAULT ''")
            if "platform" not in cols:
                alters.append("ALTER TABLE growth_products ADD COLUMN platform VARCHAR(20) DEFAULT 'amazon'")
            for sql in alters:
                conn.execute(text(sql))
            if alters:
                conn.commit()
    except Exception as e:  # 表不存在等情况交给 create_all，忽略
        print("[migrate] skipped:", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # 演示环境自举建表
    _migrate()  # 兼容已有库
    yield


app = FastAPI(
    title="Amazon AI Growth OS",
    version="1.0.0",
    description="完整版 AI 增长操作系统：发现产品 → 分析机会 → 设计产品 → 生成页面 → 投放广告 → 优化增长",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(blue_ocean.router)
app.include_router(agent_router.router)
app.include_router(tools_router.router)
app.include_router(lifecycle_router.router)
app.include_router(settings_router.router)
app.include_router(workspace_router.router)
app.include_router(profit_router.router)
app.include_router(data_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "blue-ocean-mvp"}


@app.get("/")
def index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "frontend not built; use /api/blue-ocean/research"}


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
