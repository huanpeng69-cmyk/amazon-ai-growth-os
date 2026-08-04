"""Tool：search_web —— 联网网页搜索。

调用链路：Agent → mcp.tools.search_web → BrightDataMCPClient → Bright Data。
统一返回：{"query","country","count","results":[{title,url,snippet,...}]}
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.mcp.brightdata_client.exceptions import BrightDataError
from app.mcp.tools._common import coerce_list, make_client


def search_web(
    query: str,
    country: str = "US",
    limit: int = 10,
    api_key: Optional[str] = None,
    endpoint: Optional[str] = None,
    transport: Optional[Any] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """执行网页搜索，返回归一化 JSON。

    参数
    ----
    query: 搜索词
    country: 地区码（US/DE/JP…）
    limit: 返回条数
    api_key / endpoint / transport: 测试或显式覆盖用
    """
    if not query or not query.strip():
        raise BrightDataError("search_web 需要非空的 query")
    client = make_client(api_key=api_key, endpoint=endpoint, transport=transport, timeout=timeout)
    tool = client.resolve_tool("search_web", "search_engine", "web_search")
    raw = client.call_tool(tool, {"query": query, "country": country, "limit": limit})
    items: List[Dict[str, Any]] = coerce_list(raw)[:limit]
    results: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            it = {"raw": it}
        results.append(
            {
                "title": it.get("title") or it.get("name") or "",
                "url": it.get("url") or it.get("link"),
                "snippet": it.get("snippet") or it.get("description") or it.get("body") or "",
                "source": it.get("source") or it.get("domain"),
                "position": it.get("position"),
            }
        )
    return {"query": query, "country": country, "count": len(results), "results": results}
