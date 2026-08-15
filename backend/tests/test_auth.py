"""API 鉴权依赖测试（P0-2）。

契约：
- API_AUTH_TOKEN 未配置 → 所有受保护路由开放（向后兼容本地演示）；
- 已配置 → 必须携带正确 Key（Bearer / X-API-Key / ?api_key），否则 401；
- 错误 Key → 401。
用最小 FastAPI 应用 + TestClient 隔离验证逻辑，不触发真实 agent 逻辑。
"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config_store
from app.security import get_current_key


def _make_app() -> FastAPI:
    app = FastAPI()
    @app.get("/protected", dependencies=[Depends(get_current_key)])
    def prot():
        return {"ok": True}
    return app


def test_open_when_token_unset(monkeypatch):
    monkeypatch.setitem(config_store.CONFIG, "API_AUTH_TOKEN", "")
    c = TestClient(_make_app())
    assert c.get("/protected").status_code == 200


def test_401_when_token_set_but_missing(monkeypatch):
    monkeypatch.setitem(config_store.CONFIG, "API_AUTH_TOKEN", "secret")
    c = TestClient(_make_app())
    assert c.get("/protected").status_code == 401


def test_ok_with_bearer(monkeypatch):
    monkeypatch.setitem(config_store.CONFIG, "API_AUTH_TOKEN", "secret")
    c = TestClient(_make_app())
    r = c.get("/protected", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200


def test_ok_with_x_api_key(monkeypatch):
    monkeypatch.setitem(config_store.CONFIG, "API_AUTH_TOKEN", "secret")
    c = TestClient(_make_app())
    r = c.get("/protected", headers={"X-API-Key": "secret"})
    assert r.status_code == 200


def test_ok_with_query_key(monkeypatch):
    monkeypatch.setitem(config_store.CONFIG, "API_AUTH_TOKEN", "secret")
    c = TestClient(_make_app())
    r = c.get("/protected", params={"api_key": "secret"})
    assert r.status_code == 200


def test_401_with_wrong_key(monkeypatch):
    monkeypatch.setitem(config_store.CONFIG, "API_AUTH_TOKEN", "secret")
    c = TestClient(_make_app())
    r = c.get("/protected", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
