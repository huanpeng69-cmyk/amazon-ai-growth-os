"""统一错误响应与全局异常处理。

目标（P1-1）：
- 任意未捕获异常 / 校验失败 / HTTPException 都返回**一致的 JSON** 错误体（而非 FastAPI 默认 HTML）；
- 每次请求带唯一 ``trace_id``，回写在响应头 ``X-Trace-Id`` 与 JSON 体内，便于跨服务串联排查；
- 生产环境默认**不泄露内部细节/堆栈**（仅 `EXPOSE_ERRORS=1` 或 APP_ENV=debug 才带）。

错误体结构：
    {"error": "internal"|"bad_request"|"not_found"|..., "message": "...", "trace_id": "..."}
    {"error": "validation_error", "message": "...", "trace_id": "...", "details": [ {...}, ... ]}
"""
from __future__ import annotations

import logging
import os
import traceback

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("aigos.errors")


def _trace_id(request: Request) -> str:
    # 由 TraceIDMiddleware 写入 request.state（跨异常边界比 contextvars 更稳）。
    return getattr(request.state, "trace_id", "") or ""


def _is_debug() -> bool:
    """是否向客户端暴露内部错误细节 / 堆栈。

    默认关闭（生产安全）。仅显式 `EXPOSE_ERRORS=1` 时开启。
    """
    return os.getenv("EXPOSE_ERRORS", "0") == "1"


def _error_body(error: str, message: str, trace_id: str, details=None) -> dict:
    body = {"error": error, "message": message}
    if trace_id:
        body["trace_id"] = trace_id
    if details is not None:
        body["details"] = details
    return body


def _strip_status(exc: HTTPException) -> str:
    """把 HTTPException 映射到稳定的错误类型（不暴露原始类名）。"""
    code = exc.status_code
    if code == status.HTTP_401_UNAUTHORIZED:
        return "unauthorized"
    if code == status.HTTP_403_FORBIDDEN:
        return "forbidden"
    if code == status.HTTP_404_NOT_FOUND:
        return "not_found"
    if code == status.HTTP_429_TOO_MANY_REQUESTS:
        return "rate_limited"
    if code >= 500:
        return "internal"
    return "bad_request"


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    trace_id = _trace_id(request)
    resp = JSONResponse(
        status_code=exc.status_code,
        content=_error_body(_strip_status(exc), str(exc.detail), trace_id),
    )
    # 保留上层（如限流）已设置的 Retry-After / X-RateLimit-* 头
    for k, v in (exc.headers or {}).items():
        resp.headers[k] = v
    if trace_id:
        resp.headers["X-Trace-Id"] = trace_id
    return resp


def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    trace_id = _trace_id(request)
    details = [
        {"loc": list(getattr(e, "loc", ())), "msg": getattr(e, "msg", ""), "type": getattr(e, "type", "")}
        for e in exc.errors()
    ]
    resp = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body("validation_error", "请求参数校验失败", trace_id, details),
    )
    if trace_id:
        resp.headers["X-Trace-Id"] = trace_id
    return resp


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = _trace_id(request)
    # 服务端永远记录完整堆栈，便于排障；extra 显式带 trace_id 以对齐 JSON 日志字段
    logger.error(
        "未捕获异常 path=%s: %s", request.url.path, exc, exc_info=True,
        extra={"trace_id": trace_id, "request_id": trace_id},
    )
    message = "服务器内部错误，请稍后重试或凭 trace_id 联系支持"
    if _is_debug():
        message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    resp = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("internal", message, trace_id),
    )
    if trace_id:
        resp.headers["X-Trace-Id"] = trace_id
    return resp


def install_exception_handlers(app: FastAPI) -> None:
    """在 app 上挂载统一异常处理器。

    注意：兜底用 ``StarletteHTTPException`` 而非 ``Exception`` —— Starlette 中
    ``Exception`` 不被当作任意异常的兜底，只有挂在 ``StarletteHTTPException`` 上才能
    同时捕获 FastAPI 的 HTTPException 与路由级 404（Starlette 默认 404）。
    """
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
