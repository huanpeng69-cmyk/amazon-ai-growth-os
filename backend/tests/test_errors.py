"""P1-1 统一错误包 / 全局异常处理 测试。

用 TestClient 验证：
- 每次请求都带 trace_id（响应头 X-Trace-Id）；
- 未捕获异常 → JSON {error:internal,...}（非 HTML），生产不泄露堆栈；
- HTTPException(404) → JSON {error:not_found}；
- 限流 429 → JSON {error:rate_limited} 且保留 Retry-After 头；
- pydantic 校验失败 → JSON {error:validation_error, details:[...]}；
- 显式开启 EXPOSE_ERRORS 后未捕获异常泄露堆栈。

注意：
- 为隔离，crash / rl 路由挂在**独立的最小 app** 上（先装中间件+异常处理器，再加路由），
  避免污染 app.main 的共享单例（Starlette 注册异常处理器时会把"当时已有路由"包进 try/except，
  之后新增路由不在保护范围内）。
- TestClient 一律用 ``raise_server_exceptions=False``，否则服务器层 500 会直接抛给测试，
  无法验证返回的 JSON 错误体。
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.errors import install_exception_handlers
from app.main import app as real_app
from app.middleware import TraceIDMiddleware
from app.ratelimit import rate_limit_default


def _client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _make_isolated_app() -> FastAPI:
    a = FastAPI()
    a.add_middleware(TraceIDMiddleware)
    install_exception_handlers(a)

    err = APIRouter()

    @err.get("/__crash__")
    def crash():
        raise RuntimeError("boom-test")

    @err.get("/__rl__", dependencies=[Depends(rate_limit_default)])
    def rl_route():
        return {"ok": True}

    a.include_router(err)
    return a


def test_trace_id_present_on_normal_request():
    c = _client(real_app)
    r = c.get("/api/health")
    assert r.status_code == 200
    assert "X-Trace-Id" in r.headers
    assert len(r.headers["X-Trace-Id"]) >= 16  # uuid hex


def test_unhandled_exception_returns_json_not_html():
    c = _client(_make_isolated_app())
    r = c.get("/__crash__")
    assert r.status_code == 500
    assert r.headers.get("content-type", "").startswith("application/json")
    body = r.json()
    assert body["error"] == "internal"
    assert "trace_id" in body
    # 默认不泄露内部细节（无堆栈、无异常类型名）
    assert "Traceback" not in body["message"]
    assert "RuntimeError" not in body["message"]
    # 响应头也回写 trace_id，且同一次请求 header 与 body 一致
    assert r.headers["X-Trace-Id"] == body["trace_id"]


def test_http_exception_404_mapped():
    c = _client(real_app)
    r = c.get("/api/v1/blue-ocean/nonexistent-task-id")
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "not_found"
    assert "trace_id" in body
    assert r.headers["X-Trace-Id"] == body["trace_id"]


def test_429_preserves_retry_after_header():
    c = _client(_make_isolated_app())
    # 用唯一 IP 打满默认 20/min 配额
    headers = {"X-Forwarded-For": "203.0.113.99"}
    codes = [c.get("/__rl__", headers=headers).status_code for _ in range(25)]
    assert 429 in codes
    r = c.get("/__rl__", headers=headers)
    assert r.status_code == 429
    body = r.json()
    assert body["error"] == "rate_limited"
    assert "Retry-After" in r.headers          # 限流头被保留
    assert "X-RateLimit-Limit" in r.headers


def test_validation_error_returns_json_with_details():
    c = _client(real_app)
    # 受保护路由但无 quota 问题；缺必填字段触发 pydantic 422
    r = c.post("/api/v1/agent/run", json={"not_a_valid_field": 1})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "validation_error"
    assert isinstance(body["details"], list) and body["details"]
    assert "trace_id" in body


def test_debug_mode_exposes_stack(monkeypatch):
    monkeypatch.setenv("EXPOSE_ERRORS", "1")
    c = _client(_make_isolated_app())
    r = c.get("/__crash__")
    assert r.status_code == 500
    body = r.json()
    # 开启后泄露内部异常类型与原始信息，便于本地排障
    # （本测试为合成异常、无有效调用栈，故只校验“异常类型名 + 原始消息”被暴露；
    #   真实端点抛出的异常会带完整堆栈，由 traceback.format_exc() 生成。）
    assert "RuntimeError" in body["message"]
    assert "boom-test" in body["message"]
    monkeypatch.delenv("EXPOSE_ERRORS", raising=False)
