"""Tool 层后端选择配置。

后端类型来自运行时配置存储（config_store）：默认 mock，可在前端设置界面
切到 mcp / api / local_model。Agent 调用方无需改动。
"""
from __future__ import annotations

import os

from app.config_store import get as _cfg

DEFAULT_BACKEND = os.getenv("TOOL_DEFAULT_BACKEND", "mock")


def backend_for(name: str) -> str:
    """返回某工具当前应使用的后端类型字符串（运行时读取，前端可即时切换）。"""
    key = "TOOL_BACKEND_" + name.upper()
    return _cfg(key, DEFAULT_BACKEND) or DEFAULT_BACKEND

