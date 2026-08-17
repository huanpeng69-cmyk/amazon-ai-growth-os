"""API 版本化契约测试（P2-3）。

约定：所有业务接口统一挂在 /api/v1 下；/api/health 作为元端点保持
向后兼容（不版本化）。本测试锁定该契约，防止回归把路由写回未版本化前缀。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as app_main


def _paths():
    return set(app_main.app.openapi()["paths"].keys())


def test_all_business_routes_under_v1():
    paths = _paths()
    # 业务路由 = /api/ 下且非 /api/health 元端点
    business = [p for p in paths if p.startswith("/api/") and p != "/api/health"]
    # 业务路由必须全部在 /api/v1 下
    assert all(p.startswith("/api/v1/") for p in business), business
    assert len(business) >= 1


def test_no_unversioned_business_prefix():
    paths = _paths()
    # 不允许出现 /api/agent、/api/blue-ocean 等裸前缀（已迁移到 /api/v1）
    stray = [
        p
        for p in paths
        if p.startswith("/api/")
        and not p.startswith("/api/v1/")
        and p != "/api/health"
    ]
    assert stray == [], f"发现未版本化业务路由: {stray}"


def test_health_endpoint_stays_unversioned():
    paths = _paths()
    assert "/api/health" in paths
    assert "/api/v1/health" not in paths  # health 不重复版本化


def test_old_unversioned_path_is_gone():
    c = TestClient(app_main.app)
    # 旧的 /api/settings/status（无 v1）应 404，证明已迁移
    r = c.get("/api/settings/status")
    assert r.status_code == 404


def test_v1_path_is_registered():
    c = TestClient(app_main.app)
    # 版本化后的端点应当存在（200/401/403 均可，关键是「不是 404」）
    r = c.get("/api/v1/settings/status")
    assert r.status_code != 404
