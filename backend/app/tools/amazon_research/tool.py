"""amazon_research 工具定义。"""
from __future__ import annotations

from app.tools.base import BackendType, BaseTool
from app.tools.amazon_research.schemas import AmazonResearchInput, AmazonResearchOutput
from app.tools.amazon_research.backends import (
    AmazonResearchBackend,
    McpAmazonResearchBackend,
    ApiAmazonResearchBackend,
)


class AmazonResearchTool(BaseTool):
    name = "amazon_research"
    description = "AI 蓝海市场挖掘：国家 + 类目 + 预算 → Top-N 潜力产品（规模/竞争/痛点/评分/建议）"
    input_model = AmazonResearchInput
    output_model = AmazonResearchOutput
    _backends = {
        BackendType.MOCK: AmazonResearchBackend,
        BackendType.MCP: McpAmazonResearchBackend,
        BackendType.API: ApiAmazonResearchBackend,
    }
