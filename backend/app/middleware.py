"""请求级 trace_id 中间件。

- 每个请求分配唯一 ``trace_id``：优先复用客户端传入的 ``X-Request-Id`` / ``X-Trace-Id``，否则生成 UUID；
- 写入 ``request.state.trace_id``（异常处理器从此读取，跨异常边界比 contextvars 更稳），并回写响应头 ``X-Trace-Id``。
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


def _incoming_trace_id(request: Request) -> str:
    for header in ("x-trace-id", "x-request-id"):
        val = request.headers.get(header)
        if val:
            # 仅取安全片段，避免注入超长/异常值
            return val.strip()[:64]
    return uuid.uuid4().hex


class TraceIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = _incoming_trace_id(request)
        # 写入 request.state（异常处理器从此读取，跨异常边界更稳）
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
