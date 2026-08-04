"""Connector 注册表。

各 Connector 在自己的包 __init__ 中调用 register() 自注册，避免中心化 import 造成循环依赖。
DAL / Agent 通过 get(name) 取得 Connector 实例（自动注入 config_store 中的凭证配置）。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Type

from app.data.base import BaseConnector
from app.data.exceptions import ConnectorNotConfigured


class ConnectorRegistry:
    _registry: Dict[str, Type[BaseConnector]] = {}

    @classmethod
    def register(cls, name: str, connector_cls: Type[BaseConnector]) -> None:
        cls._registry[name] = connector_cls

    @classmethod
    def get(cls, name: str, config: Optional[dict] = None) -> BaseConnector:
        if name not in cls._registry:
            raise ConnectorNotConfigured(f"未知 Connector: {name}（已注册：{cls.list()}）")
        cfg = config or cls._connector_config(name)
        return cls._registry[name](cfg)

    @classmethod
    def list(cls) -> List[str]:
        return sorted(cls._registry.keys())

    @classmethod
    def _connector_config(cls, name: str) -> dict:
        from app.config_store import get_connector_config

        return get_connector_config(name)
