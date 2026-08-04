"""Bright Data MCP 手动联调脚本（真实联网测试）。

前置：在 .env 或环境变量配置 BRIGHTDATA_API_KEY（与 BRIGHTDATA_ENDPOINT，默认 mcp.brightdata.com）。
      确保项目 venv 已激活：backend/venv/Scripts/python.exe

示例（在 backend/ 目录下）：
    # Amazon 商品研究
    venv/Scripts/python.exe scripts/run_brightdata_mcp.py amazon --keyword "cat water fountain" --country US --limit 5
    # 网页搜索
    venv/Scripts/python.exe scripts/run_brightdata_mcp.py search --query "best cat fountain 2026"
    # 网页抓取
    venv/Scripts/python.exe scripts/run_brightdata_mcp.py scrape --url https://www.example.com

输出为工具统一 JSON（结构见 app/mcp/tools/*）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# 让脚本能从 backend/ 直接以 `python scripts/run_brightdata_mcp.py` 运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config_store import get as cfg_get  # noqa: E402
from app.mcp.brightdata_client.exceptions import BrightDataError  # noqa: E402
from app.mcp.tools.amazon_research import amazon_research  # noqa: E402
from app.mcp.tools.scrape_page import scrape_page  # noqa: E402
from app.mcp.tools.search_web import search_web  # noqa: E402


def _emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Bright Data MCP 手动联调")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_amz = sub.add_parser("amazon", help="Amazon 商品研究")
    p_amz.add_argument("--keyword", required=True)
    p_amz.add_argument("--country", default="US")
    p_amz.add_argument("--limit", type=int, default=10)

    p_sch = sub.add_parser("search", help="网页搜索")
    p_sch.add_argument("--query", required=True)
    p_sch.add_argument("--country", default="US")
    p_sch.add_argument("--limit", type=int, default=10)

    p_scr = sub.add_parser("scrape", help="网页抓取")
    p_scr.add_argument("--url", required=True)
    p_scr.add_argument("--format", default="markdown", choices=["markdown", "html"])

    args = parser.parse_args()

    if not cfg_get("BRIGHTDATA_API_KEY"):
        print("✗ 未检测到 BRIGHTDATA_API_KEY。请先在 .env 配置后重试。", file=sys.stderr)
        return 2

    try:
        if args.cmd == "amazon":
            _emit(amazon_research(keyword=args.keyword, country=args.country, limit=args.limit))
        elif args.cmd == "search":
            _emit(search_web(query=args.query, country=args.country, limit=args.limit))
        elif args.cmd == "scrape":
            _emit(scrape_page(url=args.url, format=args.format))
    except BrightDataError as e:
        print(f"✗ Bright Data 错误：{e.message}（HTTP {e.status_code}）", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
