"""P2-5 image_generation 真实后端 + 诚实降级测试。

锁定：
- Mock 后端只产出「规划」（无伪造的真实图片 URL）。
- WisArt(API) 后端缺密钥 → 抛 ToolNotConfigured（501），绝不编造。
- Agnes 后端：有 Key 走真实生图返回真实 URL；无 Key / 调用失败 → 占位说明且
  image_url=None，绝不伪造真实图片。
- ImageAgent 端到端集成产出结构化计划。
"""
from __future__ import annotations

import sys
from unittest import mock

import pytest

from app.agents.image.agent import ImageAgent
from app.agents.image.schemas import ImageGenAgentInput
from app.tools.base import ToolNotConfigured
from app.tools.image_generation.tool import ImageGenerationTool

# app.llm.__init__ 把 agnes 实例重导出到包命名空间，遮蔽了同名子模块；
# 因此直接取 sys.modules 里的真实模块对象来打补丁。
_AGNES_MODULE = sys.modules["app.llm.agnes"]


def _run(backend: str, **overrides) -> dict:
    payload = {
        "product_name": "Foldable Travel Kettle",
        "niche_keyword": "travel",
        "style": "ecommerce",
        "count": 4,
        "platform": "amazon",
    }
    payload.update(overrides)
    return ImageGenerationTool(backend=backend).run(payload)


# ───────────────────── Mock（离线规划，诚实） ─────────────────────
def test_mock_backend_returns_plan_without_fabricated_url():
    out = _run("mock")
    assert len(out["images"]) == 4
    assert out["images"][0]["scene"] == "主图白底"
    assert out["images"][0]["aspect_ratio"] == "1:1"
    # Mock 后端只给规划，不给伪造的真实图片 URL
    for img in out["images"]:
        assert img.get("image_url") is None


# ───────────────────── WisArt API（真实后端） ─────────────────────
def test_wisart_api_missing_key_raises_not_configured(monkeypatch):
    monkeypatch.delenv("WISART_API_KEY", raising=False)
    with pytest.raises(ToolNotConfigured):
        _run("api")


# ───────────────────── Agnes（真实后端） ─────────────────────
def test_agnes_missing_key_returns_placeholder_no_fake_url(monkeypatch):
    fake = mock.MagicMock()
    fake.enabled.return_value = False  # 等价于 AGNES_API_KEY 未设置
    monkeypatch.setattr(_AGNES_MODULE, "agnes", fake)
    out = _run("agnes")
    for img in out["images"]:
        assert img["image_url"] is None
        assert "占位" in img["description"] or "AGNES_API_KEY" in img["description"]


def test_agnes_with_key_returns_real_url(monkeypatch):
    fake = mock.MagicMock()
    fake.enabled.return_value = True
    fake.generate_image.return_value = [
        {"url": "https://agnes.example/img/1.png", "b64_json": None}
    ]
    monkeypatch.setattr(_AGNES_MODULE, "agnes", fake)
    out = _run("agnes", count=1)
    assert out["images"][0]["image_url"] == "https://agnes.example/img/1.png"


def test_agnes_generate_failure_stays_honest(monkeypatch):
    """生图调用抛错时，降级为占位说明 + image_url=None，绝不返回伪造 URL。"""
    fake = mock.MagicMock()
    fake.enabled.return_value = True
    fake.generate_image.side_effect = RuntimeError("upstream 503")
    monkeypatch.setattr(_AGNES_MODULE, "agnes", fake)
    out = _run("agnes", count=1)
    assert out["images"][0]["image_url"] is None
    assert "失败" in out["images"][0]["description"]


# ───────────────────── MCP 后端（未接入 → 诚实 501） ─────────────────────
def test_mcp_backend_not_configured():
    with pytest.raises(ToolNotConfigured):
        _run("mcp")


# ───────────────────── ImageAgent 端到端 ─────────────────────
def test_image_agent_integration_produces_structured_plan():
    out = ImageAgent().run(ImageGenAgentInput(
        product_name="Foldable Travel Kettle",
        niche_keyword="travel",
        count=4,
    ))
    assert out.product_name == "Foldable Travel Kettle"
    assert len(out.shots) == 4
    assert out.shots[0].purpose == "主图"
    assert 0 <= out.readiness_score <= 100
