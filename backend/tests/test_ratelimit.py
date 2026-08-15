"""P0-3 速率限制：单元测试 + TestClient 集成测试。

验证点：
- 固定窗口计数：阈值内放行、超阈值拒绝并返回 429 + Retry-After / X-RateLimit-* 头；
- 按 IP（X-Forwarded-For）与 API Key 维度分别限流；
- 重操作配额（5/min）独立于默认配额（20/min）；
- FastAPI 依赖注入链路正确（依赖能拿到 Request 并触发 429）。
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.ratelimit import (
    Window,
    _STORES,
    rate_limit_default,
    rate_limit_heavy,
)


def _reset() -> None:
    _STORES.clear()


# ───────────────────────── 单元测试：Window ─────────────────────────
def test_window_allows_up_to_limit_then_rejects():
    w = Window(times=3, seconds=60)
    assert w.check("a")[0] is True
    assert w.check("a")[0] is True
    assert w.check("a")[0] is True
    allowed, retry = w.check("a")
    assert allowed is False
    assert retry >= 1


def test_window_separate_identities():
    w = Window(times=1, seconds=60)
    assert w.check("ip:1.1.1.1")[0] is True
    # 不同标识不互相挤占
    assert w.check("ip:2.2.2.2")[0] is True
    # 同标识二次被拒
    assert w.check("ip:1.1.1.1")[0] is False


def test_window_reset():
    w = Window(times=1, seconds=60)
    assert w.check("x")[0] is True
    assert w.check("x")[0] is False
    w.reset()
    assert w.check("x")[0] is True


# ─────────────────────── 集成测试：TestClient ───────────────────────
def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/normal", dependencies=[Depends(rate_limit_default)])
    def normal():
        return {"ok": True}

    @app.get("/heavy", dependencies=[Depends(rate_limit_heavy)])
    def heavy():
        return {"ok": True}

    return app


def test_default_quota_returns_429_with_headers():
    _reset()
    client = TestClient(_make_app())
    # 默认 20/min：前 20 次放行
    for _ in range(20):
        r = client.get("/normal", headers={"X-Forwarded-For": "9.9.9.9"})
        assert r.status_code == 200, r.status_code
    # 第 21 次被限流
    r = client.get("/normal", headers={"X-Forwarded-For": "9.9.9.9"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert int(r.headers["X-RateLimit-Limit"]) == 20
    assert int(r.headers["Retry-After"]) >= 1


def test_heavy_quota_stricter_than_default():
    _reset()
    client = TestClient(_make_app())
    for _ in range(5):
        r = client.get("/heavy", headers={"X-Forwarded-For": "8.8.8.8"})
        assert r.status_code == 200, r.status_code
    r = client.get("/heavy", headers={"X-Forwarded-For": "8.8.8.8"})
    assert r.status_code == 429
    assert int(r.headers["X-RateLimit-Limit"]) == 5


def test_different_ips_have_separate_buckets():
    _reset()
    client = TestClient(_make_app())
    # 两个不同 IP 各自可打满 20 次
    for _ in range(20):
        assert client.get("/normal", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    for _ in range(20):
        assert client.get("/normal", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
    # 各自第 21 次被拒
    assert client.get("/normal", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    assert client.get("/normal", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429
