"""FastAPI 应用入口。

- 启动建表
- 挂载蓝海挖掘 API
- 在 / 提供单页前端（零构建可演示）
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.security import get_current_key
from app.ratelimit import rate_limit_default


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

def _cors_origins() -> list[str]:
    """可配置的 CORS 来源白名单。

    - 默认仅放行同源 / 本地回环地址（后端自托管前端时即为同源）；
    - 需跨域自托管时，用环境变量 CORS_ALLOW_ORIGINS 传逗号分隔的源列表；
    - 仅当用户显式设置为 ``*`` 才放开为通配（不推荐对外暴露）。
    """
    raw = os.getenv("CORS_ALLOW_ORIGINS", "")
    if raw.strip() == "*":
        return ["*"]
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    # 默认回环地址（覆盖常见本地端口与调试端口）
    defaults = [
        "http://127.0.0.1:8002",
        "http://localhost:8002",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]
    seen = set()
    out = []
    for o in defaults + origins:
        if o not in seen:
            seen.add(o)
            out.append(o)
    return out


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

# 受保护路由：统一要求 API Key（若已配置 API_AUTH_TOKEN）。
# /api/health 与 / 静态资源不在此列，保持开放。
_PROTECTED_ROUTERS = [
    blue_ocean,
    agent_router,
    tools_router,
    lifecycle_router,
    workspace_router,
    profit_router,
    data_router,
]
# 受保护路由：统一要求 API Key（若已配置 API_AUTH_TOKEN）+ 默认速率限制。
# /api/health 与 / 静态资源不在此列，保持开放。
for _m in _PROTECTED_ROUTERS:
    app.include_router(
        _m.router,
        dependencies=[Depends(get_current_key), Depends(rate_limit_default)],
    )

# settings 路由有独立的 SETTINGS_API_TOKEN 写保护，不叠加全局 API Key。
app.include_router(settings_router.router)


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
