"""Ads Connector —— 广告 / PPC 指标。

真实数据源：Amazon Advertising API（Sponsored Products / Brands / Display 报表）。
fixture：connectors/ads_connector/fixtures/sample.json（真实样本，非随机生成）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.data.base import BaseConnector, RawData
from app.data.exceptions import ConnectorNotConfigured, DataNotFound


class AdsConnector(BaseConnector):
    name = "ads"
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "sample.json"

    # 复用 BaseConnector.fetch 模板（live 优先，未就绪自动降级 fixture）
    def fetch(self, query: Dict[str, Any]) -> RawData:
        return BaseConnector.fetch(self, query)

    def _fetch_live(self, query: Dict[str, Any]) -> RawData:
        # TODO(Phase 1 live): 接入 Amazon Advertising API 报表
        raise ConnectorNotConfigured(
            f"{self.name} 的 LiveAdapter 尚未实现：请配置 ADS_CONNECTOR_API_KEY 并接入广告 API"
        )

    def _fetch_fixture(self, query: Dict[str, Any]) -> RawData:
        data = self._load_fixture()
        asin = query.get("asin")
        country = (query.get("country") or "US")
        ads = data.get("by_asin", {}).get(asin) or data.get("default")
        if not ads:
            raise DataNotFound(f"ads_connector 未找到广告数据：asin={asin}")
        ads = dict(ads)
        ads.setdefault("country", country)
        ads.setdefault("asin", asin)
        return RawData(
            connector=self.name,
            query=query,
            source="fixture",
            payload={"country": country, "asin": asin, "ads": ads},
        )
