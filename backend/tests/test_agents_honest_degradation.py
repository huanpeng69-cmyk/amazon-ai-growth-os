"""Agent 诚实降级契约测试（集成风格，外部依赖全部 mock）。

这是 P0-1 最关键的一组测试：锁定「绝不编造」这条产品底线。
每个被审查过的 agent 都必须在缺少真实数据时**诚实告知**，而不是炮制数字：

1. Competitor：est_market_share 永远为 None（无真实份额数据源），
   无真实竞品时 summary 明确告知「未能检索到真实竞品数据」。
2. Advertising：无真实广告指标时，每条 metric 的 value 为 "N/A"、
   efficiency_score 为 None、summary 声明「暂未获取到真实广告表现数据」。
3. Sales Forecast：未提供销量且 Bright Data 不可用时，units 为带强声明的规划占位值，
   basis 必须含 ⚠️ 披露「未获取到真实需求信号」。
"""
from __future__ import annotations

from unittest import mock

import pytest

from app.agents._util import llm_available
from app.agents.advertising.tools import analyze_ads
from app.agents.competitor.agent import CompetitorAgent
from app.agents.competitor.schemas import CompetitorInput
from app.agents.competitor.tools import scan_competitors
from app.agents.sales_forecast.agent import SalesForecastAgent
from app.agents.sales_forecast.schemas import SalesForecastInput


# ───────────────────────── Competitor ─────────────────────────
def test_competitor_never_fabricates_market_share():
    canned = {
        "profiles": [
            {"name": "A", "price_usd": 19.9, "avg_reviews": 100, "rating": 4.3,
             "est_market_share": None, "weakness": "电池续航短"},
            {"name": "B", "price_usd": 25.0, "avg_reviews": 200, "rating": 4.5,
             "est_market_share": None, "weakness": "噪音大"},
        ],
        "summary": "格局总结",
    }
    with mock.patch(
        "app.agents.competitor.agent.COMPETITOR_TOOLS",
        [{"name": "scan_competitors", "handler": lambda *a, **k: canned}],
    ):
        out = CompetitorAgent().run(CompetitorInput(niche_keyword="wireless earbuds"))
    assert out.competitors, "应有竞品输出"
    for c in out.competitors:
        # 核心不变量：份额永远不编造
        assert c.est_market_share is None


def test_scan_competitors_tool_sets_share_none():
    """更底层地证明：即便有真实抓取的竞品，工具也只置 None，不套用递减份额公式。"""
    prods = [{"name": "P1", "price_usd": 10.0, "avg_reviews": 50, "rating": 4.0}]
    with mock.patch("app.agents.competitor.tools._live_competitors", return_value=prods), \
         mock.patch("app.agents.competitor.tools._gather_reviews", return_value={}), \
         mock.patch("app.agents.competitor.tools._llm_summary", return_value="s"), \
         mock.patch("app.agents.competitor.tools.llm_available", return_value=False):
        res = scan_competitors("kw")
    assert res["profiles"]
    for p in res["profiles"]:
        assert p["est_market_share"] is None


def test_competitor_no_data_summary_is_honest():
    empty = {"profiles": [], "summary": "未能从 Amazon 检索到「x」的真实竞品数据。"}
    with mock.patch(
        "app.agents.competitor.agent.COMPETITOR_TOOLS",
        [{"name": "scan_competitors", "handler": lambda *a, **k: empty}],
    ):
        out = CompetitorAgent().run(CompetitorInput(niche_keyword="x"))
    assert out.competitors == []
    assert "未能" in out.summary and "真实竞品数据" in out.summary


# ───────────────────────── Advertising ─────────────────────────
class _Ads:
    acos = 24.0
    roas = 3.6
    ctr = 0.8
    cvr = 12.0
    spend = 500
    ad_sales = 2000
    orders = 80


def _patch_adv_env(with_data: bool):
    """逐个 patch analyze_ads 的模块级依赖（整体 patch 模块不会重定向函数 globals）。"""
    patchers = [
        mock.patch("app.agents.advertising.tools.SessionLocal"),
        mock.patch("app.agents.advertising.tools.dal"),
        mock.patch("app.agents.advertising.tools._agnes"),
    ]
    started = [p.start() for p in patchers]
    dal, agnes = started[1], started[2]
    dal.list_products.return_value = (
        [mock.MagicMock(asin="B1", price=29.9, title="Widget")] if with_data else []
    )
    dal.get_ads.return_value = _Ads() if with_data else None
    dal.get_reviews.return_value = []
    agnes.enabled.return_value = False  # 走确定性英文模板，避免依赖实时 LLM
    return patchers


def test_advertising_no_data_shows_na_not_fabricated():
    patchers = _patch_adv_env(with_data=False)
    try:
        out = analyze_ads("wireless earbuds", country="US")
    finally:
        for p in patchers:
            p.stop()
    # 无真实广告指标 → 每条都应是 N/A，绝不出现伪造的 24.0%/3.6x
    assert out["efficiency_score"] is None
    for met in out["metrics"]:
        assert met["value"] == "N/A", f"{met['key']} 应为 N/A 而非编造值"
    assert "暂未获取到真实广告表现数据" in out["summary"]


def test_advertising_real_data_is_preserved():
    patchers = _patch_adv_env(with_data=True)
    try:
        out = analyze_ads("wireless earbuds", country="US")
    finally:
        for p in patchers:
            p.stop()
    # 有真实数据时应展示真实指标，而非 N/A
    assert out["efficiency_score"] is not None
    vals = {met["key"]: met["value"] for met in out["metrics"]}
    assert vals["ACOS"] != "N/A" and vals["ACOS"].startswith("24.0")
    assert vals["ROAS"] != "N/A"


# ───────────────────────── Sales Forecast ─────────────────────────
def test_sales_forecast_no_data_disclosure():
    with mock.patch("app.agents.sales_forecast.agent._real_demand_base", return_value=None):
        out = SalesForecastAgent().run(
            SalesForecastInput(product_name="x", selling_price=29.9, net_profit_per_unit=5.0)
        )
    assert out.estimated_monthly_units == 200  # 规划占位值
    assert "⚠️" in out.basis
    assert "未获取到真实需求信号" in out.basis


def test_sales_forecast_provided_units_used():
    out = SalesForecastAgent().run(
        SalesForecastInput(
            product_name="x", selling_price=29.9, net_profit_per_unit=5.0, provided_units=500
        )
    )
    assert out.estimated_monthly_units == 500
    assert "用户/上游提供" in out.basis


def test_sales_forecast_brightdata_signal():
    with mock.patch("app.agents.sales_forecast.agent._real_demand_base", return_value=300):
        out = SalesForecastAgent().run(
            SalesForecastInput(
                product_name="x", selling_price=29.9, net_profit_per_unit=5.0,
                category="Pets", competitor_price=29.9, ad_acos=0.15, competition_level="medium",
            )
        )
    assert out.estimated_monthly_units != 200
    assert "Bright Data" in out.basis
