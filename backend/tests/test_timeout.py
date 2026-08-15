"""P1-4 同步阻塞 / 超时治理测试。

- 阻塞调用经 run_blocking_with_timeout 在线程执行，超阈值返回 504（JSON timeout）；
- RequestTimeoutError 专用处理器映射为 504 且带 X-Trace-Id；
- 并发调用经 asyncio.to_thread 真正并行（事件循环不被阻塞）。
"""
from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import install_exception_handlers
from app.middleware import TraceIDMiddleware
from app.timeout import RequestTimeoutError, run_blocking_with_timeout


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)
    install_exception_handlers(app)

    @app.get("/fast")
    async def fast():
        return await run_blocking_with_timeout(time.sleep, 0.01, timeout=5)

    @app.get("/slow")
    async def slow():
        return await run_blocking_with_timeout(time.sleep, 2.0, timeout=1)

    @app.get("/boom")
    async def boom():
        raise RequestTimeoutError("故意超时")

    return app


_client = TestClient(_make_app())


def test_fast_call_ok():
    r = _client.get("/fast")
    assert r.status_code == 200


def test_slow_call_returns_504_timeout_json():
    r = _client.get("/slow")
    assert r.status_code == 504
    body = r.json()
    assert body["error"] == "timeout"
    assert "X-Trace-Id" in r.headers


def test_request_timeout_handler_is_registered():
    r = _client.get("/boom")
    assert r.status_code == 504
    assert r.json()["error"] == "timeout"


def test_concurrent_blocking_calls_run_in_parallel():
    """5 个各 0.3s 的阻塞调用经 to_thread 并发，总耗时远小于串行 1.5s。"""
    async def _main():
        start = time.monotonic()
        await asyncio.gather(
            *[run_blocking_with_timeout(time.sleep, 0.3, timeout=5) for _ in range(5)]
        )
        return time.monotonic() - start

    elapsed = asyncio.new_event_loop().run_until_complete(_main())
    assert elapsed < 1.5, f"并发未生效，耗时 {elapsed:.2f}s（应接近 0.3s）"
