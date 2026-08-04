"""Image Connector —— 商品/竞品/参考图。

真实数据源：Amazon 商品图 CDN / 图库 API（如 Unsplash）/ 用户上传。
fixture：connectors/image_connector/fixtures/sample.json（真实样本图地址，非随机生成）。

注意：image_connector 提供的是「图片数据输入」（供视觉生成/分析参考），
与 image_generation（生图）是上下游关系——前者取真实图，后者基于真实图生成方案。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.data.base import BaseConnector, RawData
from app.data.exceptions import ConnectorNotConfigured, DataNotFound


class ImageConnector(BaseConnector):
    name = "image"
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "sample.json"

    # 复用 BaseConnector.fetch 模板（live 优先，未就绪自动降级 fixture）
    def fetch(self, query: Dict[str, Any]) -> RawData:
        return BaseConnector.fetch(self, query)

    def _fetch_live(self, query: Dict[str, Any]) -> RawData:
        # TODO(Phase 1 live): 接入 Amazon 商品图 CDN / 图库 API
        raise ConnectorNotConfigured(
            f"{self.name} 的 LiveAdapter 尚未实现：请配置 IMAGE_CONNECTOR_API_KEY/ENDPOINT 并接入图源"
        )

    def _fetch_fixture(self, query: Dict[str, Any]) -> RawData:
        data = self._load_fixture()
        asin = query.get("asin")
        kind = (query.get("kind") or "reference")
        key = asin or query.get("query") or "default"

        images = data.get("by_key", {}).get(key)
        if not images:
            images = [img for img in data.get("pool", []) if img.get("kind") == kind]
        if not images:
            images = data.get("pool", [])
        if not images:
            raise DataNotFound(f"image_connector 未找到图片：key={key}, kind={kind}")
        return RawData(
            connector=self.name,
            query=query,
            source="fixture",
            payload={"kind": kind, "asin": asin, "images": images},
        )
