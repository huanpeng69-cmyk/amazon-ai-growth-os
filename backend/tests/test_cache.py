"""P2-1 缓存层测试。

- TTLCache 单测：get/set、过期、FIFO 淘汰、get_or_set、TTL<=0 关闭；
- Market Research Agent 集成：相同输入二次调用命中缓存（cached=True），
  且昂贵外部调用（Bright Data + LLM）只发生一次。
"""
from __future__ import annotations

import time

from app.agents.market_research.agent import MarketResearchAgent
from app.agents.market_research.schemas import MarketResearchInput
from app.cache import TTLCache, research_cache


def _fake_report_json() -> str:
    return """{
      "market_size": {"tier": "中", "monthly_usd_estimate": 120000, "rationale": "基于样本均价与销量"},
      "competitor_count": 5,
      "price_range": {"min": 10.0, "max": 30.0, "avg": 20.0, "currency": "USD", "note": "中端价位"},
      "top_products": [{"product_name": "X", "why_top": "高评分高评论"}],
      "opportunities": [{"title": "机会A", "detail": "d", "evidence": "e"}],
      "entry_recommendation": "建议进入",
      "summary": "摘要"
    }"""


def test_ttlcache_set_get_and_expiry():
    c = TTLCache(maxsize=10, default_ttl=1)
    c.set("k", "v")
    assert c.get("k") == "v"
    time.sleep(1.2)
    assert c.get("k") is None  # 过期


def test_ttlcache_fifo_eviction():
    c = TTLCache(maxsize=2, default_ttl=600)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)  # 触发淘汰最旧 a
    assert c.get("a") is None
    assert c.get("b") == 2 and c.get("c") == 3


def test_ttlcache_get_or_set_and_disabled():
    c = TTLCache(maxsize=10, default_ttl=600)
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return "val"

    v1, hit1 = c.get_or_set("x", factory)
    v2, hit2 = c.get_or_set("x", factory)
    assert v1 == v2 == "val"
    assert hit1 is False and hit2 is True
    assert calls["n"] == 1  # factory 只调用一次

    disabled = TTLCache(maxsize=10, default_ttl=0)
    disabled.set("y", "z")
    assert disabled.get("y") is None  # TTL<=0 不缓存


def test_market_research_cache_hit_avoids_external_calls(monkeypatch):
    research_cache._store.clear()
    agent = MarketResearchAgent()

    products = [
        {"title": f"P{i}", "price": f"{10 + i}", "rating": f"4.{i}", "reviews": f"{100 + i}"}
        for i in range(8)
    ]
    # 注意：agent.py 内 `from app.mcp.tools.amazon_research import amazon_research`
    # 把函数名绑定进了自身命名空间；`app.mcp.tools.amazon_research` 是 __init__
    # 的再导出（同名函数，会遮蔽子模块），所以必须 patch agent 模块内的名字。
    monkeypatch.setattr(
        "app.agents.market_research.agent.amazon_research",
        lambda keyword=None, country=None, limit=None: {"products": products},
    )
    calls = {"chat": 0}

    def _fake_chat(*a, **k):
        calls["chat"] += 1
        return _fake_report_json()

    # `app.llm.__init__` 把 agnes 实例再导出到 app.llm 命名空间，
    # 因此 patch 必须是 agent 模块内绑定的实例方法（agnes.chat），
    # 而非 app.llm.agnes.agnes（那会退化成“模块里有同名子模块”的误匹配）。
    monkeypatch.setattr(
        "app.agents.market_research.agent.agnes.chat",
        _fake_chat,
    )

    inp = MarketResearchInput(country="US", category="Pets", keyword="cat tree", limit=20)
    r1 = agent.run(inp)
    r2 = agent.run(inp)

    assert r1.cached is False
    assert r2.cached is True  # 命中缓存
    # 缓存命中时不重跑昂贵外部调用：LLM 只被调用一次（首次）
    assert calls["chat"] == 1, f"缓存未生效，LLM 被调用 {calls['chat']} 次"
    research_cache._store.clear()
