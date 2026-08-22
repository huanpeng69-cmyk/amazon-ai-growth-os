"""MCP Tool 层 —— 基类与后端抽象。

设计原则：
1. 不复制外部开源源码 —— 本层只定义「接口契约」与「后端适配器」，
   真实实现（Bright Data / Sorftime / Sif / easy-amazon-voc / ecom-details-image 等）
   通过 MCP Server / REST API / 本地模型 三种后端接入，源码不入库。
2. 模块化封装 —— 每个工具是独立目录（schemas / tool / backends）。
3. 保留替换能力 —— 同一个工具可在 mock / mcp / api / local_model 间切换，
   切换仅改配置（环境变量），不改动调用方（Agent）代码。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, ValidationError


class BackendType(str, Enum):
    """工具后端类型。未来新增后端只需扩展此枚举并在工具里注册适配器。"""
    MOCK = "mock"            # 本地确定性实现（离线演示 / 兜底）
    MCP = "mcp"              # 外部 MCP Server（如 Bright Data / Sorftime / Sif / easy-amazon-voc）
    API = "api"              # 外部 REST API（密钥鉴权，如 SellerSprite / Stability / WisArt）
    LOCAL_MODEL = "local_model"  # 本地模型（开源权重，如 SDXL / 本地 LLM 分类）
    AGNES = "agnes"          # Agnes AI 文生图（复用已配置的 AgnesClient 图像模型）


class ToolError(Exception):
    """工具执行错误，携带 HTTP 状态码。"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class ToolNotConfigured(ToolError):
    """后端未配置（未来能力尚未接入）。返回 501。"""

    def __init__(self, message: str):
        super().__init__(message, status_code=501)


class ToolBackend(ABC):
    """后端适配器：把统一的工具调用翻译为目标实现。

    每个工具可注册多个后端（mock / mcp / api / local_model）。
    新增后端 = 继承此类实现 execute()，并在工具的 ``_backends`` 注册。
    """

    backend_type: BackendType

    def __init__(self, config: dict | None = None):
        # config 来自运行时（环境变量 / 密钥 / MCP server 命令等）
        self.config: dict = config or {}

    @abstractmethod
    def execute(self, params: dict) -> dict:
        """执行工具，返回「输出 JSON」对应的 dict。"""
        raise NotImplementedError

    # —— 通用 MCP 调用骨架（future）——
    # 真实实现用 MCP 客户端（如 mcp Python SDK）连接 server_command 指定的 MCP Server，
    # 通过 stdio 或 SSE 调用 tool_name(arguments)。此处仅保留接口形态，不实现具体传输。
    def _call_mcp_skeleton(self, server_command: str, tool_name: str, arguments: dict) -> dict:
        raise NotImplementedError(
            "MCP 后端骨架未实现：请接入 MCP 客户端（stdio/SSE），"
            f"server={server_command}, tool={tool_name}"
        )


class BaseTool(ABC):
    """工具基类。子类必须定义：name / description / input_model / output_model / _backends。"""

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    _backends: dict[BackendType, type[ToolBackend]]

    def __init__(self, backend: str | BackendType = "mock", config: dict | None = None):
        bt = BackendType(backend) if isinstance(backend, str) else backend
        adapter_cls = self._backends.get(bt)
        if adapter_cls is None:
            avail = ", ".join(b.value for b in self._backends)
            raise ToolNotConfigured(
                f"工具 '{self.name}' 不支持后端 '{bt.value}'；可用后端：{avail}"
            )
        self.backend_type = bt
        self.backend = adapter_cls(config or {})

    @property
    def input_schema(self) -> dict:
        """输入 JSON Schema（对接 MCP / 前端表单自动生成）。"""
        return self.input_model.model_json_schema()

    @property
    def output_schema(self) -> dict:
        """输出 JSON Schema。"""
        return self.output_model.model_json_schema()

    def run(self, input: dict) -> dict:
        """统一执行入口：校验输入 JSON → 后端执行 → 校验输出 JSON → 返回 dict。"""
        try:
            validated = self.input_model.model_validate(input)
        except ValidationError as e:
            raise ToolError(f"输入校验失败: {e}") from e

        raw = self.backend.execute(validated.model_dump())

        try:
            out = self.output_model.model_validate(raw)
        except ValidationError as e:
            raise ToolError(f"输出校验失败（后端返回结构不正确）: {e}") from e

        return out.model_dump()
