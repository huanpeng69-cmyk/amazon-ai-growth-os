"""market_search 工具定义。"""
from __future__ import annotations

from app.tools.base import BackendType, BaseTool
from app.tools.market_search.schemas import MarketSearchInput, MarketSearchOutput
from app.tools.market_search.backends import (
    MarketSearchBackend,
    McpMarketSearchBackend,
    ApiMarketSearchBackend,
)


class MarketSearchTool(BaseTool):
    name = "market_search"
    description = "市场信号检索：国家 + 类目 → 候选利基原始信号（搜索量/价格/竞品/评论/增速/痛点）"
    input_model = MarketSearchInput
    output_model = MarketSearchOutput
    _backends = {
        BackendType.MOCK: MarketSearchBackend,
        BackendType.MCP: McpMarketSearchBackend,
        BackendType.API: ApiMarketSearchBackend,
    }
