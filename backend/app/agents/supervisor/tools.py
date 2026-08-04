"""Supervisor Agent —— 工具接口。

Supervisor 可调度的 4 个专家 Agent（工具）。每个工具含 name/description/
input_schema(JSON Schema)/handler（实际执行子 Agent）。handler 接收 dict 参数，
由 Supervisor 在派发时构造。
"""
from __future__ import annotations

from app.agents.advertising.agent import AdvertisingAgent
from app.agents.advertising.schemas import AdvertisingInput
from app.agents.competitor.agent import CompetitorAgent
from app.agents.competitor.schemas import CompetitorInput
from app.agents.image.agent import ImageAgent
from app.agents.image.schemas import ImageGenAgentInput
from app.agents.listing.agent import ListingAgent
from app.agents.listing.schemas import ListingInput
from app.agents.market.agent import MarketAgent
from app.agents.market.schemas import MarketInput
from app.agents.market_research.agent import MarketResearchAgent
from app.agents.market_research.schemas import MarketResearchInput
from app.agents.product.agent import ProductAgent
from app.agents.product.schemas import ProductInput
from app.agents.voc.agent import VOCAgent
from app.agents.voc.schemas import VOCInput
from app.agents.visual_agent.agent import VisualAgent
from app.agents.visual_agent.schemas import VisualAgentInput


def call_market_agent(params: dict):
    return MarketAgent().run(MarketInput(**params))


def call_market_research_agent(params: dict):
    return MarketResearchAgent().run(MarketResearchInput(**params))


def call_competitor_agent(params: dict):
    return CompetitorAgent().run(CompetitorInput(**params))


def call_voc_agent(params: dict):
    return VOCAgent().run(VOCInput(**params))


def call_product_agent(params: dict):
    return ProductAgent().run(ProductInput(**params))


def call_listing_agent(params: dict):
    return ListingAgent().run(ListingInput(**params))


def call_image_agent(params: dict):
    return ImageAgent().run(ImageGenAgentInput(**params))


def call_advertising_agent(params: dict):
    return AdvertisingAgent().run(AdvertisingInput(**params))


def call_visual_agent(params: dict):
    return VisualAgent().run(VisualAgentInput(**params))


SUPERVISOR_TOOLS = [
    {
        "name": "call_market_agent",
        "description": "调用 Market Agent 做蓝海市场挖掘，返回 Top-N 潜力产品。",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "category": {"type": "string"},
                "budget_usd": {"type": "integer"},
                "top_n": {"type": "integer", "default": 10},
            },
            "required": ["country", "category", "budget_usd"],
        },
        "handler": call_market_agent,
    },
    {
        "name": "call_market_research_agent",
        "description": "调用 Market Research Agent：经 Bright Data 取数 + 数据清洗 + AI 分析，产出市场调研报告（市场规模/竞品数/价格区间/头部产品/机会点/进入建议）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string", "default": "US"},
                "category": {"type": "string"},
                "keyword": {"type": "string", "default": ""},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["category"],
        },
        "handler": call_market_research_agent,
    },
    {
        "name": "call_competitor_agent",
        "description": "调用 Competitor Agent 做竞品分析，返回头部竞品格局与软肋。",
        "input_schema": {
            "type": "object",
            "properties": {
                "niche_keyword": {"type": "string"},
                "country": {"type": "string", "default": "US"},
                "top_n": {"type": "integer", "default": 5},
            },
            "required": ["niche_keyword"],
        },
        "handler": call_competitor_agent,
    },
    {
        "name": "call_voc_agent",
        "description": "调用 VOC Agent 做用户声音分析，返回痛点排序与改进建议。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "country": {"type": "string", "default": "US"},
            },
            "required": ["product_name"],
        },
        "handler": call_voc_agent,
    },
    {
        "name": "call_product_agent",
        "description": "调用 Product Agent 做产品机会判断，返回结论与推荐定位。",
        "input_schema": {
            "type": "object",
            "properties": {
                "niche_keyword": {"type": "string"},
                "country": {"type": "string", "default": "US"},
                "budget_usd": {"type": "integer", "default": 5000},
            },
            "required": ["niche_keyword"],
        },
        "handler": call_product_agent,
    },
    {
        "name": "call_listing_agent",
        "description": "调用 Listing Agent 生成高转化 Listing 文案与图片方案。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "niche_keyword": {"type": "string", "default": ""},
                "key_features": {"type": "array", "items": {"type": "string"}},
                "tone": {"type": "string", "enum": ["专业可信", "年轻活力", "高端奢华"]},
            },
            "required": ["product_name"],
        },
        "handler": call_listing_agent,
    },
    {
        "name": "call_image_agent",
        "description": "调用 Image Agent 规划主图到附图的电商视觉生成方案。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "niche_keyword": {"type": "string", "default": ""},
                "style": {"type": "string", "enum": ["ecommerce", "lifestyle", "minimal"]},
                "count": {"type": "integer", "default": 6},
            },
            "required": ["product_name"],
        },
        "handler": call_image_agent,
    },
    {
        "name": "call_advertising_agent",
        "description": "调用 Advertising Agent 做 PPC 广告分析与优化建议。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "niche_keyword": {"type": "string", "default": ""},
                "country": {"type": "string", "default": "US"},
                "budget_usd": {"type": "integer", "default": 0},
            },
            "required": ["product_name"],
        },
        "handler": call_advertising_agent,
    },
    {
        "name": "call_visual_agent",
        "description": "调用 Product Visual Agent：策略优先生成 7 张 Listing 图片方案 + Prompt + 生成请求 + 质量评分。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "niche_keyword": {"type": "string", "default": ""},
                "market_positioning": {"type": "string", "default": ""},
                "voc_pain_points": {"type": "array", "items": {"type": "string"}, "default": []},
                "competitor_insights": {"type": "string", "default": ""},
                "style": {"type": "string", "enum": ["ecommerce", "lifestyle", "minimal"]},
                "country": {"type": "string", "default": "US"},
            },
            "required": ["product_name"],
        },
        "handler": call_visual_agent,
    },
]
