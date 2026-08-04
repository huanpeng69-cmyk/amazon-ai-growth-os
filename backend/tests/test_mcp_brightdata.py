"""Bright Data MCP 接入的离线单测（无需联网）。

运行方式（在 backend/ 目录下，使用项目 venv）：
    cd amazon-ai-growth-os/backend
    ../venv/Scripts/python.exe -m pytest tests/test_mcp_brightdata.py -q

测试覆盖：
- MCP 客户端：initialize / tools/list / resolve_tool / call_tool 解包
- 三个 Tool 的归一化（search_web / scrape_page / amazon_research）
- 全链路 Agent → Tool → MCP → Bright Data（用 MockTransport 模拟 Bright Data）
- AmazonConnector._fetch_live 经 mcp.tools.amazon_research 取数 + 无凭证降级
"""
from __future__ import annotations

import json
from unittest import mock

from app.mcp.brightdata_client.client import BrightDataMCPClient, MockTransport
from app.mcp.brightdata_client.exceptions import BrightDataToolNotFound
from app.mcp.tools.amazon_research import amazon_research
from app.mcp.tools.scrape_page import scrape_page
from app.mcp.tools.search_web import search_web


def _wrap_text(obj) -> dict:
    """模拟 Bright Data tools/call 返回：content[].text = JSON 字符串。"""
    return {"content": [{"type": "text", "text": json.dumps(obj)}]}


def _mock_client(tools_call_result, tools_list=None):
    tools = tools_list or [
        {"name": "amazon_search"},
        {"name": "search_web"},
        {"name": "scrape_as_markdown"},
    ]
    t = MockTransport()
    t.on("tools/list", lambda p: {"tools": tools})
    t.on("tools/call", lambda p: tools_call_result)
    return BrightDataMCPClient(transport=t, auto_init=False)


# ───────────── MCP 客户端 ─────────────
def test_initialize_and_list_tools():
    t = MockTransport()
    t.on("initialize", lambda p: {"protocolVersion": "2024-11-05", "capabilities": {}})
    t.on("tools/list", lambda p: {"tools": [{"name": "amazon_search"}]})
    client = BrightDataMCPClient(transport=t, auto_init=False)
    assert client._initialize()["protocolVersion"] == "2024-11-05"
    assert [x["name"] for x in client.list_tools()] == ["amazon_search"]


def test_resolve_tool_substring_match():
    client = _mock_client(_wrap_text({"products": []}), tools_list=[{"name": "amazon_search"}])
    assert client.resolve_tool("amazon_search", "amazon_product") == "amazon_search"


def test_resolve_tool_not_found():
    client = _mock_client(_wrap_text({"products": []}), tools_list=[{"name": "foo"}])
    try:
        client.resolve_tool("amazon_search")
        assert False, "应当抛出 BrightDataToolNotFound"
    except BrightDataToolNotFound:
        pass


def test_call_tool_unwraps_json():
    client = _mock_client(_wrap_text({"hello": "world"}))
    assert client.call_tool("amazon_search", {"keyword": "x"}) == {"hello": "world"}


# ───────────── search_web ─────────────
def test_search_web_normalize():
    raw = {"results": [
        {"title": "T1", "url": "https://a.com", "snippet": "s1"},
        {"title": "T2", "url": "https://b.com", "snippet": "s2"},
    ]}
    client = _mock_client(_wrap_text(raw))
    out = search_web("cat fountain", transport=client._transport)
    assert out["query"] == "cat fountain"
    assert out["count"] == 2
    assert out["results"][0]["title"] == "T1"
    assert out["results"][1]["url"] == "https://b.com"


# ───────────── scrape_page ─────────────
def test_scrape_page_returns_content():
    client = _mock_client({"content": [{"type": "text", "text": "# Markdown\nbody"}]})
    out = scrape_page("https://example.com", transport=client._transport)
    assert out["url"] == "https://example.com"
    assert out["content"].startswith("# Markdown")


# ───────────── amazon_research（统一 JSON）─────────────
def test_amazon_research_unified_shape():
    raw_products = {"products": [
        {"asin": "B0ABC123", "title": "Cat Water Fountain", "price": "$29.99",
         "rating": "4.6", "reviews": "1820", "category": "Pet Supplies"},
        {"ASIN": "B0XYZ999", "name": "Dog Bed", "current_price": 19.9,
         "stars": 4.2, "review_count": 540, "category_name": "Dogs"},
    ]}
    client = _mock_client(_wrap_text(raw_products))
    out = amazon_research("cat water fountain", transport=client._transport)
    assert out["count"] == 2
    p0 = out["products"][0]
    # 必须包含统一字段
    for k in ("asin", "title", "price", "rating", "reviews", "category", "url"):
        assert k in p0, f"缺少字段 {k}"
    assert p0["asin"] == "B0ABC123"
    assert p0["price"] == "29.99"          # 价格统一为字符串
    assert p0["rating"] == 4.6             # 数值化
    assert p0["reviews"] == 1820           # 整数化
    assert p0["url"] == "https://www.amazon.com/dp/B0ABC123"
    # 第二个商品字段名差异也应被归一
    p1 = out["products"][1]
    assert p1["asin"] == "B0XYZ999"
    assert p1["title"] == "Dog Bed"
    assert p1["rating"] == 4.2
    assert p1["reviews"] == 540


# ───────────── AmazonConnector 集成（mock Tool 层）─────────────
def test_connector_live_uses_mcp_tool():
    from app.data.connectors.amazon_connector.connector import AmazonConnector

    with mock.patch(
        "app.config_store.get",
        lambda k, d="": "KEY" if k == "BRIGHTDATA_API_KEY" else (d or ""),
    ), mock.patch(
        "app.mcp.tools.amazon_research.amazon_research",
        lambda **kw: {
            "keyword": kw.get("keyword"), "country": kw.get("country"), "count": 1,
            "products": [{
                "asin": "B0LIVE1", "title": "Live Product", "price": "$15.00",
                "rating": 4.3, "reviews": 300, "category": "Pet",
                "url": "https://www.amazon.com/dp/B0LIVE1"}],
        },
    ):
        conn = AmazonConnector(config={"mode": "auto"})
        assert conn.mode == "live"  # auto + BRIGHTDATA_API_KEY → live
        raw = conn._fetch_live({"keyword": "cat fountain", "country": "US"})
        assert raw.source == "live"
        prod = raw.payload["products"][0]
        # 映射为 parse_amazon 期望字段
        assert prod["asin"] == "B0LIVE1"
        assert prod["review_count"] == 300   # reviews → review_count
        assert prod["rating"] == 4.3


def test_connector_degrade_without_key():
    from app.data.connectors.amazon_connector.connector import AmazonConnector
    from app.data.exceptions import ConnectorNotConfigured

    # 无 BRIGHTDATA_API_KEY → _fetch_live 抛 ConnectorNotConfigured（基类自动降级 fixture）
    with mock.patch(
        "app.config_store.get",
        lambda k, d="": "" if k == "BRIGHTDATA_API_KEY" else (d or ""),
    ):
        conn = AmazonConnector(config={"mode": "auto"})
        assert conn.mode == "fixture"
        try:
            conn._fetch_live({"keyword": "cat fountain", "country": "US"})
            assert False, "无凭证应抛 ConnectorNotConfigured"
        except ConnectorNotConfigured:
            pass


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            print(f"✓ {fn.__name__}")
            passed += 1
        except Exception:  # noqa: BLE001
            print(f"✗ {fn.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n结果：{passed} 通过 / {failed} 失败 / 共 {len(fns)}")
    raise SystemExit(1 if failed else 0)
