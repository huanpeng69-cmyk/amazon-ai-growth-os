"""多 Agent 串联流水线测试（LangGraph StateGraph）。

全部 mock 三个 Agent 的 .run()，不触发任何外部调用（Bright Data / LLM）。
覆盖：
1. 正常链路：状态正确传递，Listing 的 key_features 来自 Product.reasons，全步成功。
2. 市场调研失败：记录错误，但 Product / Listing 仍运行（诚实降级）。
3. 产品判断失败：Listing 的 key_features 回退到 MR.opportunities 标题。
"""
from __future__ import annotations

import pytest

from app.agents.listing.agent import ListingAgent
from app.agents.listing.schemas import ListingOutput
from app.agents.market_research.agent import MarketResearchAgent
from app.agents.market_research.schemas import (
    MarketResearchReport,
    MarketSizeJudgment,
    OpportunityPoint,
    PriceRange,
    TopProductSummary,
)
from app.agents.product.agent import ProductAgent
from app.agents.product.schemas import ProductOutput
from app.pipelines import ResearchToListingPipeline
from app.pipelines.schemas import PipelineInput


def _mr_report() -> MarketResearchReport:
    return MarketResearchReport(
        country="US", category="Pets", keyword="cat toy",
        market_size=MarketSizeJudgment(tier="中", rationale="样本规模中等"),
        competitor_count=12,
        price_range=PriceRange(min=9.9, max=29.9, avg=18.0, note="中端价位"),
        top_products=[TopProductSummary(product_name="Cat Teaser", why_top="高评分高复购")],
        opportunities=[OpportunityPoint(
            title="耐用材质缺口", detail="现有产品易坏", evidence="差评多提材质脆弱")],
        entry_recommendation="可进入", summary="稳中有机会",
    )


def _prod_out() -> ProductOutput:
    return ProductOutput(
        niche_keyword="cat toy", verdict="推荐", opportunity_score=72,
        reasons=["需求稳定", "竞争中等", "痛点明确"],
        recommended_positioning="以耐用为核心卖点",
    )


def _listing_out() -> ListingOutput:
    return ListingOutput(
        product_name="Cat Teaser", tone="专业可信", title="Durable Cat Teaser Toy",
        bullet_points=["1", "2"], description="desc", search_terms=["cat toy"],
        completeness_score=88.0,
    )


def _run(monkeypatch, *, mr=None, prod=None, listing=None, capture_listing=None):
    monkeypatch.setattr(MarketResearchAgent, "run",
                        lambda self, inp: mr() if callable(mr) else mr)
    monkeypatch.setattr(ProductAgent, "run",
                        lambda self, inp: prod() if callable(prod) else prod)
    if capture_listing is not None:
        def spy(self, inp):
            capture_listing["inp"] = inp
            return listing if not callable(listing) else listing()
        monkeypatch.setattr(ListingAgent, "run", spy)
    else:
        monkeypatch.setattr(ListingAgent, "run",
                            lambda self, inp: listing() if callable(listing) else listing)
    return ResearchToListingPipeline().run(
        PipelineInput(country="US", category="Pets", keyword="cat toy", budget_usd=5000))


def test_happy_path_state_passes(monkeypatch):
    captured = {}
    res = _run(monkeypatch, mr=_mr_report, prod=_prod_out,
               listing=_listing_out, capture_listing=captured)

    assert res.errors == []
    assert res.market_report is not None
    assert res.product_result is not None
    assert res.listing_result is not None
    # 状态传递验证：Listing 的 key_features 来自 Product.reasons
    assert captured["inp"].key_features == ["需求稳定", "竞争中等", "痛点明确"]


def test_market_research_failure_degrades(monkeypatch):
    captured = {}

    def boom(self, inp):
        raise RuntimeError("Bright Data 503")

    res = _run(monkeypatch, mr=boom, prod=_prod_out,
               listing=_listing_out, capture_listing=captured)

    assert any("market_research" in e for e in res.errors)
    assert res.market_report is None
    # 下游仍运行（诚实降级）
    assert res.product_result is not None
    assert res.listing_result is not None
    # MR 缺失时，Listing 卖点回退到 Product.reasons
    assert captured["inp"].key_features == ["需求稳定", "竞争中等", "痛点明确"]


def test_product_failure_listing_uses_mr_opportunities(monkeypatch):
    captured = {}

    def boom(self, inp):
        raise RuntimeError("score engine down")

    res = _run(monkeypatch, mr=_mr_report, prod=boom,
               listing=_listing_out, capture_listing=captured)

    assert any("product" in e for e in res.errors)
    assert res.product_result is None
    assert res.listing_result is not None
    # Product 缺失时，Listing 卖点回退到 MR.opportunities 标题
    assert captured["inp"].key_features == ["耐用材质缺口"]
