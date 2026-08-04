"""Agent 总控 API 路由（Supervisor 派发）+ 各 Agent 直调入口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..agents.advertising.agent import AdvertisingAgent
from ..agents.advertising.schemas import AdvertisingInput, AdvertisingOutput
from ..agents.competitor.agent import CompetitorAgent
from ..agents.competitor.schemas import CompetitorInput, CompetitorOutput
from ..agents.image.agent import ImageAgent
from ..agents.image.schemas import ImageGenAgentInput, ImageGenAgentOutput
from ..agents.listing.agent import ListingAgent
from ..agents.listing.schemas import ListingInput, ListingOutput
from ..agents.market_research.agent import MarketResearchAgent
from ..agents.market_research.schemas import MarketResearchInput, MarketResearchReport
from ..agents.supervisor.agent import SupervisorAgent
from ..agents.supervisor.schemas import AgentRunResult, SupervisorInput
from ..agents.voc.agent import VOCAgent
from ..agents.voc.schemas import VOCInput, VOCOutput
from ..agents.visual_agent.agent import VisualAgent
from ..agents.visual_agent.schemas import VisualAgentInput, VisualAgentOutput
from ..llm.agnes import AgnesError
from ..routers.workspace import fill_input, load_product_for, store_module_output
from ..database import get_db
from ..tools.base import ToolNotConfigured

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/run", response_model=AgentRunResult)
def run_agent(req: SupervisorInput, db=Depends(get_db)) -> AgentRunResult:
    """自然语言需求 → Supervisor 判断意图 → 派发对应专家 Agent → 汇总结果。

    若结果含竞品分析，且存在活动产品，则把竞品产出回写产品空间（mod_competitor），
    供下游模块（Listing/视觉/广告）在联动时复用。
    """
    result = SupervisorAgent().run(req.query)
    if getattr(result, "competitor", None):
        prod = load_product_for(db, None)
        if prod:
            comp = getattr(result, "competitor")
            store_module_output(
                db, prod, "competitor", comp.model_dump(mode="json"),
                identity={"niche_keyword": getattr(comp, "niche_keyword", ""),
                          "country": getattr(comp, "country", "US")},
            )
    return result


@router.post("/listing", response_model=ListingOutput)
def run_listing(req: ListingInput, db=Depends(get_db)):
    """Listing Agent 直调：产品+利基+卖点 → 高转化 Listing + 图片方案。"""
    prod = load_product_for(db, req.product_id)
    if prod:
        req = fill_input(req, prod, ["product_name", "niche_keyword", "target_country"])
    out = ListingAgent().run(req)
    if prod:
        store_module_output(db, prod, "listing", out.model_dump(mode="json"),
                             identity=req.model_dump())
    return out


@router.post("/image", response_model=ImageGenAgentOutput)
def run_image(req: ImageGenAgentInput, db=Depends(get_db)):
    """Image Agent 直调：产品+利基 → 主图到附图的生成方案 + 构图策略。"""
    prod = load_product_for(db, req.product_id)
    if prod:
        req = fill_input(req, prod, ["product_name", "niche_keyword", "platform"])
    out = ImageAgent().run(req)
    if prod:
        store_module_output(db, prod, "image", out.model_dump(mode="json"),
                             identity=req.model_dump())
    return out


@router.post("/advertising", response_model=AdvertisingOutput)
def run_advertising(req: AdvertisingInput, db=Depends(get_db)):
    """Advertising Agent 直调：产品+站点 → 核心指标 + 可执行广告动作 + 预算建议。"""
    prod = load_product_for(db, req.product_id)
    if prod:
        req = fill_input(req, prod, ["product_name", "niche_keyword", "country", "budget_usd"])
    out = AdvertisingAgent().run(req)
    if prod:
        store_module_output(db, prod, "advertising", out.model_dump(mode="json"),
                             identity=req.model_dump())
    return out


@router.post("/visual", response_model=VisualAgentOutput)
def run_visual(req: VisualAgentInput, db=Depends(get_db)):
    """Product Visual Agent 直调：策略优先 → 视觉策略 + 7图规划 + Prompt + 生成请求 + 质量评分。"""
    prod = load_product_for(db, req.product_id)
    if prod:
        req = fill_input(req, prod, ["product_name", "niche_keyword", "country", "platform"])
    out = VisualAgent().run(req)
    if prod:
        store_module_output(db, prod, "visual", out.model_dump(mode="json"),
                             identity=req.model_dump())
    return out


@router.post("/voc", response_model=VOCOutput)
def run_voc(req: VOCInput, db=Depends(get_db)):
    """VOC Agent 直调：产品/利基 → 痛点排序 + 改进建议；回写产品空间（mod_voc）供联动复用。"""
    prod = load_product_for(db, req.product_id)
    if prod and not req.product_name:
        req = VOCInput(product_name=prod.name, country=req.country, product_id=req.product_id)
    out = VOCAgent().run(req)
    if prod:
        store_module_output(
            db, prod, "voc", out.model_dump(mode="json"),
            identity={"product_name": req.product_name, "niche_keyword": prod.niche_keyword,
                      "country": req.country},
        )
    return out


@router.post("/competitor", response_model=CompetitorOutput)
def run_competitor(req: CompetitorInput, db=Depends(get_db)):
    """Competitor Agent 直调：利基 → 头部竞品格局与软肋；回写产品空间（mod_competitor）供联动复用。"""
    prod = load_product_for(db, req.product_id)
    if prod and not req.niche_keyword:
        req = CompetitorInput(niche_keyword=prod.niche_keyword, country=req.country,
                              top_n=req.top_n, product_id=req.product_id)
    out = CompetitorAgent().run(req)
    if prod:
        store_module_output(
            db, prod, "competitor", out.model_dump(mode="json"),
            identity={"niche_keyword": req.niche_keyword, "country": req.country},
        )
    return out


@router.post("/market_research", response_model=MarketResearchReport)
def run_market_research(req: MarketResearchInput, db=Depends(get_db)):
    """Market Research Agent 直调：国家 + 类目 + 关键词 → 经 Bright Data 取数、清洗、AI 分析，产出市场报告。

    约束：报告必须由 AI 生成（不返回原始数据）；缺少 AGNES_API_KEY 或 Bright Data 取数失败会明确报错。
    """
    try:
        out = MarketResearchAgent().run(req)
    except ToolNotConfigured as e:
        raise HTTPException(status_code=502, detail=str(e))
    except AgnesError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return out
