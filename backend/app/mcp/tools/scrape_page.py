"""Tool：scrape_page —— 抓取并解析网页正文。

调用链路：Agent → mcp.tools.scrape_page → BrightDataMCPClient → Bright Data。
统一返回：{"url","format","content"}（content 为 markdown/html 文本或结构化 dict）
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.mcp.brightdata_client.exceptions import BrightDataError
from app.mcp.tools._common import make_client


def scrape_page(
    url: str,
    format: str = "markdown",  # markdown | html
    api_key: Optional[str] = None,
    endpoint: Optional[str] = None,
    transport: Optional[Any] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """抓取单个网页，返回正文内容。

    参数
    ----
    url: 目标网页地址
    format: 返回格式（markdown 默认，或 html）
    """
    if not url or not str(url).strip():
        raise BrightDataError("scrape_page 需要非空的 url")
    client = make_client(api_key=api_key, endpoint=endpoint, transport=transport, timeout=timeout)
    tool = client.resolve_tool("scrape_as_markdown", "scrape_as_html", "scrape_page")
    args = {"url": url}
    if format == "html":
        tool = client.resolve_tool("scrape_as_html", "scrape_as_markdown", "scrape_page")
    raw = client.call_tool(tool, args)
    content = raw if isinstance(raw, (str, dict)) else str(raw)
    return {"url": url, "format": format, "content": content}
