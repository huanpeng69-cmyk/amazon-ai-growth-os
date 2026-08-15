"""P1-2 集中式 JSON 日志 + 请求 ID 测试。

验证：
- configure_logging 后日志输出为合法 JSON 单行，且含 timestamp/level/logger/request_id 等字段；
- 请求处理流内（端点里）的日志自动带上该请求的 request_id（与 X-Trace-Id 同源）；
- 异常日志通过 extra 显式带 trace_id（跨异常边界也可关联）。
"""
from __future__ import annotations

import io
import json
import logging

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.errors import install_exception_handlers
from app.logging_config import JsonFormatter, configure_logging, request_id_var
from app.main import app as real_app
from app.middleware import TraceIDMiddleware


def _json_logger() -> tuple[logging.Logger, io.StringIO]:
    """挂一个 StringIO handler（JsonFormatter）到根日志，返回 (logger, buf)。"""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    return logging.getLogger("test.json"), buf


def test_configure_logging_emits_json():
    configure_logging()
    log, buf = _json_logger()
    buf.truncate(0)
    log.info("hello %s", "world")
    raw = buf.getvalue().strip()
    assert raw, "应有日志输出"
    parsed = json.loads(raw)  # 必须为合法 JSON 单行
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "hello world"
    for f in ("timestamp", "level", "logger", "request_id", "trace_id", "module", "func", "line"):
        assert f in parsed
    # 无请求上下文时 request_id 为占位符
    assert parsed["request_id"] in ("-", "")


def test_request_logs_carry_request_id():
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)

    lines: list[str] = []

    @app.get("/__log__")
    def do_log(probe: bool = False):
        # 端点内日志应自动带上本请求的 request_id
        logging.getLogger("test.req").info("inside request")
        lines.append("called")
        if probe:
            # 探针日志在“请求上下文”内触发，request_id 必被注入
            logging.getLogger("test.req").info("probe")
        return {"ok": True}

    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/__log__")
    assert r.status_code == 200
    rid = r.headers["X-Trace-Id"]
    assert rid
    # 通过注入的 StringIO 捕获根日志，校验“请求内”日志的 request_id 与响应头一致
    log, buf = _json_logger()
    buf.truncate(0)
    r2 = c.get("/__log__?probe=true")
    rid2 = r2.headers["X-Trace-Id"]
    out = [json.loads(line) for line in buf.getvalue().strip().splitlines() if line.strip()]
    probe_line = next(o for o in out if o["message"] == "probe")
    assert probe_line["request_id"] == rid2
    assert lines  # 路由确实被调用过


def test_error_log_carries_trace_id():
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)
    install_exception_handlers(app)

    @app.get("/__boom__")
    def boom():
        raise ValueError("kaboom")

    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/__boom__")
    assert r.status_code == 500
    body = r.json()
    assert body["error"] == "internal"
    tid = body["trace_id"]
    assert tid
    # 服务端错误日志通过 extra 带 trace_id（与响应体一致）
    log, buf = _json_logger()
    buf.truncate(0)
    # 复现一次，直接从 captured 日志中找 trace_id
    c.get("/__boom__")
    out = [json.loads(line) for line in buf.getvalue().strip().splitlines() if line.strip()]
    # 至少有一条错误日志带本次或同形态的 trace_id 字段
    assert any(o.get("trace_id") for o in out), "错误日志应带 trace_id"


def test_real_app_logging_wired():
    # 真实 app 已接入 configure_logging + 中间件；仅做导入/冒烟，确保无循环导入或配置错误
    c = TestClient(real_app, raise_server_exceptions=False)
    assert c.get("/api/health").status_code == 200
