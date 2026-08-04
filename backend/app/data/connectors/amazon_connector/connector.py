"""Amazon Connector —— 商品/市场数据。

真实数据源：Amazon SP-API（Catalog Items / Product Pricing / Sales）+ Keepa（历史销量）。
fixture：connectors/amazon_connector/fixtures/sample.json（真实样本，非随机生成）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.data.base import BaseConnector, RawData
from app.data.exceptions import ConnectorNotConfigured, DataNotFound


class AmazonConnector(BaseConnector):
    name = "amazon"
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "sample.json"

    # 复用 BaseConnector.fetch 模板（live 优先，未就绪自动降级 fixture）
    def fetch(self, query: Dict[str, Any]) -> RawData:
        return BaseConnector.fetch(self, query)

    # auto 模式下，本 Connector 的 live 真实来源是 Bright Data MCP；
    # 只要配置了 BRIGHTDATA_API_KEY 即视为可走 live（覆盖基类仅看自身凭证的逻辑）。
    @property
    def mode(self) -> str:
        m = (self.config.get("mode") or "auto").lower()
        if m in ("live", "fixture"):
            return m
        from app.config_store import get as cfg_get

        if cfg_get("BRIGHTDATA_API_KEY"):
            return "live"
        if self.config.get("api_key") or self.config.get("endpoint"):
            return "live"
        return "fixture"

    def _fetch_live(self, query: Dict[str, Any]) -> RawData:
        # 链路：Agent → DAL → AmazonConnector._fetch_live
        #        → mcp.tools.amazon_research (Tool 层)
        #        → BrightDataMCPClient (MCP 层) → Bright Data
        # Agent 永不直接触达 Bright Data。
        from app.config_store import get as cfg_get
        from app.mcp.tools.amazon_research import amazon_research

        if not cfg_get("BRIGHTDATA_API_KEY"):
            raise ConnectorNotConfigured(
                f"{self.name} live 需要 BRIGHTDATA_API_KEY（经 Bright Data MCP 取数）；"
                "未配置将自动降级 fixture"
            )
        keyword = (query.get("keyword") or query.get("category") or "").strip()
        if not keyword:
            raise ConnectorNotConfigured(f"{self.name} live 需要 keyword/category")
        country = query.get("country") or "US"
        try:
            res = amazon_research(
                keyword=keyword, country=country, limit=int(query.get("limit") or 10)
            )
        except Exception as e:  # 任何 MCP/网络错误都降级 fixture，保证链路不崩
            raise ConnectorNotConfigured(f"{self.name} Bright Data 调用失败，降级 fixture：{e}")
        products = res.get("products") or []
        if not products:
            raise ConnectorNotConfigured(f"{self.name} Bright Data 未返回商品，降级 fixture")
        normalized = [self._to_parser_product(p) for p in products]
        return RawData(
            connector=self.name,
            query=query,
            source="live",
            payload={"country": country, "products": normalized},
        )

    @staticmethod
    def _to_parser_product(p: Dict[str, Any]) -> Dict[str, Any]:
        """把 Tool 层统一商品结构映射到 parse_amazon 期望的字段。"""
        return {
            "asin": p.get("asin"),
            "title": p.get("title"),
            "price": p.get("price"),
            "bsr": None,
            "est_monthly_sales": None,
            "sellers": None,
            "rating": p.get("rating"),
            "review_count": p.get("reviews"),
            "category": p.get("category"),
        }

    def _fetch_fixture(self, query: Dict[str, Any]) -> RawData:
        data = self._load_fixture()
        country = (query.get("country") or "US")
        asin = query.get("asin")
        keyword = (query.get("keyword") or query.get("category") or "").strip().lower()

        products: list = []
        by_asin = data.get("by_asin", {})
        by_keyword = data.get("by_keyword", {})

        if asin and asin in by_asin:
            products = [by_asin[asin]]
        elif keyword:
            if keyword in by_keyword:
                products = by_keyword[keyword]
            else:
                for k, v in by_keyword.items():
                    if keyword in k or k in keyword:
                        products = v
                        break

        if not products:
            raise DataNotFound(f"amazon_connector 未找到匹配数据：asin={asin}, keyword={keyword}")

        return RawData(
            connector=self.name,
            query=query,
            source="fixture",
            payload={"country": country, "products": products},
        )
