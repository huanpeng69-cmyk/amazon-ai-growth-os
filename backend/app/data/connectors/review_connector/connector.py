"""Review Connector —— 商品评论 / VOC 原料。

真实数据源：Amazon 评论 API / 第三方评论抓取（如 easy-amazon-voc）。
fixture：connectors/review_connector/fixtures/sample.json（真实样本评论，非随机生成）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.data.base import BaseConnector, RawData
from app.data.exceptions import ConnectorNotConfigured, DataNotFound


class ReviewConnector(BaseConnector):
    name = "review"
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "sample.json"

    # 复用 BaseConnector.fetch 模板（live 优先，未就绪自动降级 fixture）
    def fetch(self, query: Dict[str, Any]) -> RawData:
        return BaseConnector.fetch(self, query)

    def _fetch_live(self, query: Dict[str, Any]) -> RawData:
        # TODO(Phase 1 live): 接入 Amazon 评论 API / easy-amazon-voc
        raise ConnectorNotConfigured(
            f"{self.name} 的 LiveAdapter 尚未实现：请配置 REVIEW_CONNECTOR_API_KEY 并接入评论源"
        )

    def _fetch_fixture(self, query: Dict[str, Any]) -> RawData:
        data = self._load_fixture()
        asin = query.get("asin")
        country = (query.get("country") or "US")
        reviews = data.get("by_asin", {}).get(asin)
        if not reviews:
            raise DataNotFound(f"review_connector 未找到评论：asin={asin}")
        return RawData(
            connector=self.name,
            query=query,
            source="fixture",
            payload={"country": country, "asin": asin, "reviews": reviews},
        )
