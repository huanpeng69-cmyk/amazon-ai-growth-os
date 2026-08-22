"""多 Agent 串联流水线（LangGraph StateGraph 实现）。

节点：market_research → product → listing（顺序，无分支/循环）。
状态通道：PipelineState 在各节点间传递；上游产物通过适配器喂给下游做「富化」。

诚实降级契约（与项目一致）：
- 每个节点独立 try/except；单步失败仅记录错误、不抛出，下游照常运行。
- 各步只需顶层输入即可运行（Product 不消费 MR 报告，Listing 无卖点也能 fallback），
  因此「上游失败不阻断下游」。
- errors 用 operator.add 归约，逐步累积，最终随结果一并返回。

为何用 LangGraph：当前是线性三步，LangGraph 的图/状态通道已足够；
后续若长出分支、循环重试、human-in-the-loop，可直接在相同 StateGraph 上加边/条件边，
无需重写编排逻辑。
"""
import operator
from typing import Annotated, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.listing.agent import ListingAgent
from app.agents.listing.schemas import ListingInput, ListingOutput
from app.agents.market_research.agent import MarketResearchAgent
from app.agents.market_research.schemas import MarketResearchInput, MarketResearchReport
from app.agents.product.agent import ProductAgent
from app.agents.product.schemas import ProductInput, ProductOutput
from app.pipelines.schemas import PipelineInput, PipelineResult


class PipelineState(TypedDict):
    # —— 顶层输入（贯穿全程）——
    country: str
    category: str
    keyword: str
    budget_usd: int
    product_name: str
    tone: str
    language: str
    # —— 各步产出（被下游富化消费）——
    market_report: Optional[MarketResearchReport]
    product_result: Optional[ProductOutput]
    listing_result: Optional[ListingOutput]
    # —— 控制：逐步累积的错误（operator.add 归约）——
    errors: Annotated[list, operator.add]


def _derive_key_features(state: PipelineState) -> list:
    """从上游产物提炼 Listing 卖点（2-5 个）。

    优先级：产品机会判断的 reasons > 市场调研的 opportunities 标题 > 空列表。
    Listing Agent 在 key_features 为空时也能自行生成文案（诚实兜底）。
    """
    prod = state.get("product_result")
    if prod and getattr(prod, "reasons", None):
        return list(prod.reasons)[:5]
    mr = state.get("market_report")
    if mr and getattr(mr, "opportunities", None):
        return [o.title for o in mr.opportunities][:5]
    return []


def node_market_research(state: PipelineState) -> dict:
    try:
        out = MarketResearchAgent().run(MarketResearchInput(
            country=state["country"],
            category=state["category"],
            keyword=state["keyword"],
        ))
        return {"market_report": out}
    except Exception as e:  # 取数/LLM 失败 → 记录，下游继续
        return {"errors": [f"market_research: {e}"]}


def node_product(state: PipelineState) -> dict:
    try:
        out = ProductAgent().run(ProductInput(
            niche_keyword=state["keyword"] or state["category"],
            country=state["country"],
            budget_usd=state["budget_usd"],
        ))
        return {"product_result": out}
    except Exception as e:
        return {"errors": [f"product: {e}"]}


def node_listing(state: PipelineState) -> dict:
    try:
        out = ListingAgent().run(ListingInput(
            product_name=state["product_name"],
            niche_keyword=state["keyword"] or state["category"],
            key_features=_derive_key_features(state),
            tone=state["tone"],
            target_country=state["country"],
            language=state["language"],
        ))
        return {"listing_result": out}
    except Exception as e:
        return {"errors": [f"listing: {e}"]}


class ResearchToListingPipeline:
    """市场调研 → 产品机会判断 → Listing 生成 的串联编排器。

    接口风格与既有 Agent 一致（run(input_model) -> output_model），
    便于被 Supervisor 或前端直接触发。
    """

    name = "pipeline_research_to_listing"
    description = "多 Agent 串联：市场调研 → 产品机会判断 → Listing 生成（状态传递 + 逐级降级）"

    def __init__(self) -> None:
        self._graph = self._build()

    @staticmethod
    def _build():
        g = StateGraph(PipelineState)
        g.add_node("market_research", node_market_research)
        g.add_node("product", node_product)
        g.add_node("listing", node_listing)
        g.add_edge(START, "market_research")
        g.add_edge("market_research", "product")
        g.add_edge("product", "listing")
        g.add_edge("listing", END)
        return g.compile()

    def run(self, inp: PipelineInput) -> PipelineResult:
        product_name = inp.product_name or inp.keyword or inp.category
        init: PipelineState = {
            "country": inp.country,
            "category": inp.category,
            "keyword": inp.keyword,
            "budget_usd": inp.budget_usd,
            "product_name": product_name,
            "tone": inp.tone,
            "language": inp.language,
            "market_report": None,
            "product_result": None,
            "listing_result": None,
            "errors": [],
        }
        final = self._graph.invoke(init)
        return PipelineResult(
            country=final["country"],
            category=final["category"],
            keyword=final["keyword"],
            market_report=final.get("market_report"),
            product_result=final.get("product_result"),
            listing_result=final.get("listing_result"),
            errors=final.get("errors") or [],
        )
