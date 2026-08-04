"""Supervisor Agent —— 输入/输出 Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.agents.advertising.schemas import AdvertisingOutput
from app.agents.competitor.schemas import CompetitorOutput
from app.agents.image.schemas import ImageGenAgentOutput
from app.agents.listing.schemas import ListingOutput
from app.agents.market.schemas import MarketOutput
from app.agents.market_research.schemas import MarketResearchReport
from app.agents.product.schemas import ProductOutput
from app.agents.voc.schemas import VOCOutput
from app.agents.visual_agent.schemas import VisualAgentOutput


class SupervisorInput(BaseModel):
    query: str = Field(..., description="用户的自然语言需求")


class SupervisorPlan(BaseModel):
    intent: str = Field(..., description="market / market_research / competitor / voc / product / listing / image / advertising / visual / lifecycle / unknown")
    routed_agents: List[str]
    reason: str
    params: dict = Field(default_factory=dict)


class AgentRunResult(BaseModel):
    intent: str
    routed_agents: List[str]
    plan_reason: str
    clarification: Optional[str] = None
    params: dict = Field(default_factory=dict, description="Supervisor 抽取的结构化参数，供调用方直接复用")
    market: Optional[MarketOutput] = None
    market_research: Optional[MarketResearchReport] = None
    competitor: Optional[CompetitorOutput] = None
    voc: Optional[VOCOutput] = None
    product: Optional[ProductOutput] = None
    listing: Optional[ListingOutput] = None
    image: Optional[ImageGenAgentOutput] = None
    advertising: Optional[AdvertisingOutput] = None
    visual: Optional[VisualAgentOutput] = None
