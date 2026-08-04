"""Market Research Agent 离线测试（全程 mock：Bright Data transport + LLM）。

运行（backend/ 目录下）：
    PYTHONPATH=. ../venv/Scripts/python.exe -m pytest tests/test_market_research_agent.py -q
或： PYTHONPATH=. ../venv/Scripts/python.exe tests/test_market_research_agent.py
"""
from __future__ import annotations

from unittest import mock

from app.agents.market_research.agent import MarketResearchAgent
from app.agents.market_research.schemas import MarketResearchInput, MarketResearchReport
from app.llm.agnes import AgnesError
from app.tools.base import ToolNotConfigured


def _canned_products(n=8):
    base = [
        {"asin": f"B{ i:07d}", "title": f"Product {i}", "price": f"{10 + i}.99",
         "rating": 4.0 + (i % 5) * 0.1, "reviews": 100 * (i + 1),
         "category": "Pets", "url": f"https://www.amazon.com/dp/B{i:07d}"}
        for i in range(1, n + 1)
    ]
    return base


def _canned_llm_report():
    return (
        "```json\n"
        "{\n"
        '  "market_size": {"tier": "中", "monthly_usd_estimate": 250000, "rationale": "样本均价约15美元、评论量中位数较高，说明需求稳定中等。"},\n'
        '  "competitor_count": 8,\n'
        '  "price_range": {"min": 10.99, "max": 17.99, "avg": 14.5, "currency": "USD", "note": "主流价格带集中在10-18美元，低端竞争激烈。"},\n'
        '  "top_products": [\n'
        '    {"product_name": "Product 8", "price": "17.99", "rating": 4.4, "reviews": 800, "why_top": "高评论量叠加稳定评分，说明需求刚性且口碑稳固。"},\n'
        '    {"product_name": "Product 7", "price": "16.99", "rating": 4.3, "reviews": 700, "why_top": "评论增速快，处于上升期。"}\n'
        "  ],\n"
        '  "opportunities": [\n'
        '    {"title": "低价高评分空白", "detail": "可切入10-12美元高评分区间", "evidence": "样本均价14.5，且低价款评分普遍>=4.0"},\n'
        '    {"title": "细分功能差异化", "detail": "静音/无线方向机会", "evidence": "头部产品评论多聚焦基础功能"}\n'
        "  ],\n"
        '  "entry_recommendation": "建议以10-12美元高评分定位切入，避开17美元以上红海。",\n'
        '  "summary": "美国 Pets 类目需求中等、价格带清晰，存在低价高评分切入机会。"\n'
        "}\n"
        "```"
    )


def test_clean_aggregates():
    agent = MarketResearchAgent()
    brief = agent._clean(_canned_products(8), MarketResearchInput(country="US", category="Pets"))
    assert brief["sample_size"] == 8
    assert brief["price"]["min"] == 11.99
    assert brief["price"]["max"] == 18.99
    assert brief["price"]["currency"] == "USD"
    assert len(brief["top_products"]) == 5  # 取 top5
    # 清洗后只含分析指标，不含原始 url/asin 噪声
    assert "url" not in brief["top_products"][0]


def test_search_term_chinese_nl():
    agent = MarketResearchAgent()
    # 中文自然语言关键词在 US 站点应回退为英文类目
    inp = MarketResearchInput(country="US", category="Pets", keyword="调研一下美国宠物市场")
    assert agent._search_term(inp) == "Pets"
    # 明确英文关键词应保留
    inp2 = MarketResearchInput(country="US", category="Pets", keyword="cat water fountain")
    assert agent._search_term(inp2) == "cat water fountain"


def test_run_full_flow_mocked():
    agent = MarketResearchAgent()
    with mock.patch(
        "app.agents.market_research.agent.amazon_research",
        return_value={"keyword": "Pets", "country": "US", "count": 8, "products": _canned_products(8)},
    ), mock.patch(
        "app.llm.agnes.agnes.chat", return_value=_canned_llm_report()
    ):
        report = agent.run(MarketResearchInput(country="US", category="Pets", keyword="Pets"))
    assert isinstance(report, MarketResearchReport)
    assert report.generated_by == "ai"
    assert report.data_source == "brightdata"
    assert report.competitor_count == 8
    assert len(report.top_products) == 2
    assert len(report.opportunities) == 2
    assert report.price_range.min == 10.99
    assert report.market_size.tier == "中"
    assert report.entry_recommendation
    assert report.summary


def test_run_no_data_raises():
    agent = MarketResearchAgent()
    with mock.patch(
        "app.agents.market_research.agent.amazon_research",
        return_value={"keyword": "X", "country": "US", "count": 0, "products": []},
    ):
        try:
            agent.run(MarketResearchInput(country="US", category="Pets"))
            assert False, "无数据应抛 ToolNotConfigured"
        except ToolNotConfigured:
            pass


def test_run_no_llm_raises_not_raw():
    agent = MarketResearchAgent()
    with mock.patch(
        "app.agents.market_research.agent.amazon_research",
        return_value={"keyword": "Pets", "country": "US", "count": 8, "products": _canned_products(8)},
    ), mock.patch(
        "app.llm.agnes.agnes.chat", side_effect=AgnesError("AGNES_API_KEY 未设置")
    ):
        try:
            agent.run(MarketResearchInput(country="US", category="Pets"))
            assert False, "无 LLM 应抛 AgnesError（绝不回退原始数据）"
        except AgnesError as e:
            assert "AI" in str(e)


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn(); print(f"✓ {fn.__name__}"); passed += 1
        except Exception:  # noqa: BLE001
            print(f"✗ {fn.__name__}"); traceback.print_exc(); failed += 1
    print(f"\n结果：{passed} 通过 / {failed} 失败 / 共 {len(fns)}")
    raise SystemExit(1 if failed else 0)
