"""Connector 抽象基类与 RawData 包装。

设计要点：
- Connector 只负责「搬运」外部数据：fetch(query) → RawData（原始响应，不做业务加工）。
- 每个 Connector 内部按配置选择 adapter：
    * LiveAdapter  ：调用真实外部 API（需凭证）。未实现/无凭证时抛 ConnectorNotConfigured。
    * FixtureAdapter：加载真实样本数据集（fixtures/*.json），非随机编造。
- 业务加工（解析/归一/聚合）放到 data/processing/，不在 Connector 内。
"""
from __future__ import annotations

import json
from abc import ABC
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.data.exceptions import ConnectorNotConfigured, FixtureMissing


class RawData(BaseModel):
    """连接器原始响应包装。payload 为外部源返回的原始结构（未加工）。"""

    connector: str
    query: Dict[str, Any] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)
    source: str = "fixture"          # fixture | live
    fetched_at: Optional[str] = None


class BaseConnector(ABC):
    """连接器基类。子类必须实现 fetch()。"""

    name: str = "base"
    fixture_path: Optional[Path] = None

    def __init__(self, config: Optional[dict] = None):
        # config 来自 config_store.get_connector_config(name)
        self.config: dict = config or {}

    @property
    def mode(self) -> str:
        """运行模式：auto（有凭证走 live 否则 fixture）/ live / fixture。"""
        m = (self.config.get("mode") or "auto").lower()
        if m in ("live", "fixture"):
            return m
        # auto：有 api_key 或 endpoint 即视为可 live
        if self.config.get("api_key") or self.config.get("endpoint"):
            return "live"
        return "fixture"

    def fetch(self, query: dict) -> RawData:
        """模板方法：live 模式优先，未就绪（ConnectorNotConfigured）时自动降级 fixture。

        子类只需实现 _fetch_live / _fetch_fixture；除非需要特殊路由，否则无需覆盖本方法。
        这保证「配置错误 / LiveAdapter 未实现」时系统仍可运行（架构真实、数据非编造）。
        """
        if self.mode == "live":
            try:
                return self._fetch_live(query)
            except ConnectorNotConfigured:
                # Live 未实现或缺凭证：降级 fixture，避免整条 Agent 链路崩溃
                return self._fetch_fixture(query)
        return self._fetch_fixture(query)

    def _fetch_live(self, query: dict) -> RawData:
        """真实外部 API 拉取。子类覆盖；默认未实现。"""
        raise ConnectorNotConfigured(f"{self.name} 的 LiveAdapter 尚未实现")

    def _fetch_fixture(self, query: dict) -> RawData:
        """真实样本数据集拉取。子类必须覆盖。"""
        raise NotImplementedError

    # —— 通用 fixture 加载 ——
    def _load_fixture(self) -> dict:
        if not self.fixture_path or not Path(self.fixture_path).exists():
            raise FixtureMissing(f"{self.name} 缺少 fixture 样本数据: {self.fixture_path}")
        return json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))

    def _require_live(self) -> None:
        """Live 模式未实现或缺少凭证时调用。"""
        if not (self.config.get("api_key") or self.config.get("endpoint")):
            raise ConnectorNotConfigured(
                f"{self.name} 未配置凭证（api_key/endpoint），无法使用 live 模式"
            )
        # 有凭证但 LiveAdapter 尚未实现：子类应自行实现；此处仅作兜底提示
        raise ConnectorNotConfigured(f"{self.name} 的 LiveAdapter 尚未实现，请接入真实 API 或切换到 fixture 模式")
