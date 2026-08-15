"""P1-5 生产配置硬化测试。

- 默认（demo）启用 /docs /redoc /openapi.json；
- APP_ENV=production 时全部关闭（返回 404），避免泄露端点细节；
- CORS methods/headers 收敛为实际所需，不再通配 '*'。
"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

import app.main as app_main


def test_docs_enabled_by_default():
    assert app_main.app.docs_url == "/docs"
    c = TestClient(app_main.app)
    assert c.get("/docs").status_code == 200
    assert c.get("/openapi.json").status_code == 200


def test_production_disables_docs(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    importlib.reload(app_main)
    try:
        assert app_main.app.docs_url is None
        c = TestClient(app_main.app)
        assert c.get("/docs").status_code == 404
        assert c.get("/redoc").status_code == 404
        assert c.get("/openapi.json").status_code == 404
    finally:
        # 还原为 demo，避免影响后续测试对 app.main 的引用
        monkeypatch.delenv("APP_ENV", raising=False)
        importlib.reload(app_main)


def test_cors_methods_and_headers_tightened():
    c = TestClient(app_main.app)
    r = c.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    allow_methods = r.headers.get("access-control-allow-methods", "")
    allow_headers = r.headers.get("access-control-allow-headers", "")
    # 不再通配 '*'，仅放行实际所需
    assert "*" not in allow_methods
    assert "GET" in allow_methods and "POST" in allow_methods
    assert "x-api-key" in allow_headers.lower()
    assert "authorization" in allow_headers.lower()
