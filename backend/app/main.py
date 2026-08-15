"""FastAPI 应用入口。

- 启动建表
- 挂载蓝海挖掘 API
- 在 / 提供单页前端（零构建可演示）
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.errors import install_exception_handlers
from app.logging_config import configure_logging
from app.middleware import TraceIDMiddleware
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

# 集中式 JSON 日志（必须在创建 app / 导入 routers 之前，确保启动期日志也被结构化）
configure_logging()
logger = logging.getLogger("aigos.main")

from .migrations_run import run_migrations
from .routers import agent as agent_router
from .routers import blue_ocean
from .routers import tools as tools_router
from .routers import lifecycle as lifecycle_router
from .routers import settings as settings_router
from .routers import workspace as workspace_router
from .routers import profit as profit_router
from .routers import data as data_router

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()  # Alembic：空库自举建表 / 演进 schema（已最新则幂等返回）
    yield


app = FastAPI(
    title="Amazon AI Growth OS",
    version="1.0.0",
    description="完整版 AI 增长操作系统：发现产品 → 分析机会 → 设计产品 → 生成页面 → 投放广告 → 优化增长",
    lifespan=lifespan,
)

# 请求级 trace_id（先于路由执行，覆盖异常处理与日志）
app.add_middleware(TraceIDMiddleware)
# 统一错误包：未捕获异常 / 校验失败 / HTTPException 都返回一致 JSON（含 trace_id）
install_exception_handlers(app)

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
