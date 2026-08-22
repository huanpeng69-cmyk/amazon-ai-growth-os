"""image_generation 工具定义。"""
from __future__ import annotations

from app.tools.base import BackendType, BaseTool
from app.tools.image_generation.schemas import ImageGenInput, ImageGenOutput
from app.tools.image_generation.backends import (
    MockImageGenBackend,
    ApiImageGenBackend,
    AgnesImageGenBackend,
    LocalModelImageGenBackend,
    McpImageGenBackend,
)


class ImageGenerationTool(BaseTool):
    name = "image_generation"
    description = "电商详情页图片方案生成：产品 + 利基 → 多场景图片方案（场景/比例/提示词/说明）"
    input_model = ImageGenInput
    output_model = ImageGenOutput
    _backends = {
        BackendType.MOCK: MockImageGenBackend,
        BackendType.API: ApiImageGenBackend,  # WisArt 文生图（智画创）
        BackendType.AGNES: AgnesImageGenBackend,  # Agnes AI 文生图（复用 AgnesClient）
        BackendType.LOCAL_MODEL: LocalModelImageGenBackend,
        BackendType.MCP: McpImageGenBackend,
    }
