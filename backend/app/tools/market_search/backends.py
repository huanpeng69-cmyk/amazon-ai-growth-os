"""market_search 后端适配器。

- MarketSearchBackend：经统一数据层（DAL → amazon+keyword+review Connector）获取真实市场信号。
- McpBackend / ApiBackend：未来接入 Bright Data deep research / Google Trends API。
"""
from __future__ import annotations

from app.agents.market.tools import search_market
from app.tools.base import BackendType, ToolBackend, ToolNotConfigured


class MarketSearchBackend(ToolBackend):
    backend_type = BackendType.MOCK  # 配置键仍为 mock；数据已改为真实 Connector 来源

    def execute(self, params: dict) -> dict:
        # 复用 Market Agent 的翻译器，把真实信号转成下游约定的字段形态（含 niche_id）
        legacy = search_market(params["country"], params["category"])
        for i, s in enumerate(legacy):
            s["niche_id"] = f"{params['category']}-{i:02d}"
        return {
            "country": params["country"],
            "category": params["category"],
            "signals": legacy,
        }


class McpMarketSearchBackend(ToolBackend):
    backend_type = BackendType.MCP

    def execute(self, params: dict) -> dict:
        cmd = self.config.get("server_command") or "bright-data-deep-research-mcp"
        return self._call_mcp_skeleton(cmd, "market_search", params)


class ApiMarketSearchBackend(ToolBackend):
    backend_type = BackendType.API

    def execute(self, params: dict) -> dict:
        raise ToolNotConfigured(
            "market_search API 后端未配置：接入 Bright Data / Google Trends REST API"
        )
