"""Tool 注册表：集中管理工具，支持按配置选后端、列契约。"""
from __future__ import annotations

from typing import Type

from app.tools.base import BaseTool
from app.tools import settings


class ToolRegistry:
    _registry: dict[str, Type[BaseTool]] = {}

    @classmethod
    def register(cls, tool_cls: Type[BaseTool]) -> Type[BaseTool]:
        cls._registry[tool_cls.name] = tool_cls
        return tool_cls

    @classmethod
    def get(cls, name: str, backend: str | None = None) -> BaseTool:
        tool_cls = cls._registry.get(name)
        if tool_cls is None:
            raise KeyError(name)
        bt = backend or settings.backend_for(name)
        return tool_cls(backend=bt)

    @classmethod
    def names(cls) -> list[str]:
        return list(cls._registry)

    @classmethod
    def describe(cls, name: str) -> dict:
        tool_cls = cls._registry[name]
        inst = tool_cls(backend="mock")
        return {
            "name": tool_cls.name,
            "description": tool_cls.description,
            "backends": [b.value for b in tool_cls._backends],
            "input_schema": inst.input_schema,
            "output_schema": inst.output_schema,
        }
