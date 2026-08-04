"""Keyword Connector —— 搜索词 / 流量数据。

真实数据源：Helium 10 / SellerSprite / 卖家精灵 关键词接口。
fixture：connectors/keyword_connector/fixtures/sample.json（真实样本，非随机生成）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.data.base import BaseConnector, RawData
from app.data.exceptions import ConnectorNotConfigured, DataNotFound


class KeywordConnector(BaseConnector):
    name = "keyword"
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "sample.json"

    # 复用 BaseConnector.fetch 模板（live 优先，未就绪自动降级 fixture）
    def fetch(self, query: Dict[str, Any]) -> RawData:
        return BaseConnector.fetch(self, query)

    def _fetch_live(self, query: Dict[str, Any]) -> RawData:
        # TODO(Phase 1 live): 接入 Helium 10 / SellerSprite 关键词接口
        raise ConnectorNotConfigured(
            f"{self.name} 的 LiveAdapter 尚未实现：请配置 KEYWORD_CONNECTOR_API_KEY 并接入关键词工具"
        )

    def _fetch_fixture(self, query: Dict[str, Any]) -> RawData:
        data = self._load_fixture()
        seed = (query.get("seed_keyword") or query.get("keyword") or "").strip().lower()
        country = (query.get("country") or "US")
        keywords = data.get("by_seed_keyword", {}).get(seed)
        if not keywords:
            # 模糊匹配
            for k, v in data.get("by_seed_keyword", {}).items():
                if seed in k or k in seed:
                    keywords = v
                    break
        if not keywords:
            raise DataNotFound(f"keyword_connector 未找到关键词：seed={seed}")
        return RawData(
            connector=self.name,
            query=query,
            source="fixture",
            payload={"country": country, "seed_keyword": seed, "keywords": keywords},
        )
