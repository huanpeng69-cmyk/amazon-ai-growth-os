"""voc_analysis 工具定义。"""
from __future__ import annotations

from app.tools.base import BackendType, BaseTool
from app.tools.voc_analysis.schemas import VOCInput, VOCOutput
from app.tools.voc_analysis.backends import (
    VOCBackend,
    McpVOCBackend,
    LocalModelVOCBackend,
)


class VOCAnalysisTool(BaseTool):
    name = "voc_analysis"
    description = "用户评论 VOC 分析：利基关键词/ASIN → Top-N 用户痛点 + 改进建议 + 总结"
    input_model = VOCInput
    output_model = VOCOutput
    _backends = {
        BackendType.MOCK: VOCBackend,
        BackendType.MCP: McpVOCBackend,
        BackendType.LOCAL_MODEL: LocalModelVOCBackend,
    }
