"""voc_analysis 后端适配器。

统一改为复用 VOCAgent 的真实链路：
  Bright Data 搜索商品 → 抓取真实评论 → Agnes 大模型归纳痛点 + 给出建议。
此前此处用正则痛点词 + 硬编码 _FIX_MAP 映射建议，会出现「文不对题」，
现已通过 VOCAgent 委托给大模型，保证建议基于真实评论生成。
"""
from __future__ import annotations

from app.agents.voc.agent import VOCAgent
from app.agents.voc.schemas import VOCInput
from app.tools.base import BackendType, ToolBackend, ToolNotConfigured


class VOCBackend(ToolBackend):
    backend_type = BackendType.MOCK  # 配置键仍为 mock；逻辑已委托给 VOCAgent（真实搜索+大模型）

    def execute(self, params: dict) -> dict:
        inp = VOCInput(
            product_name=(params.get("niche_keyword") or params.get("product_name") or "").strip(),
            country=params.get("country", "US"),
        )
        out = VOCAgent().run(inp)
        return {
            "niche_keyword": inp.product_name,
            "country": out.country,
            "pain_points": [
                {
                    "pain": p.pain,
                    "severity": p.severity,
                    "evidence": p.evidence,
                    "suggested_fix": p.suggested_fix,
                }
                for p in out.pain_points
            ],
            "summary": out.summary,
        }


class McpVOCBackend(ToolBackend):
    backend_type = BackendType.MCP

    def execute(self, params: dict) -> dict:
        cmd = self.config.get("server_command") or "easy-amazon-voc-mcp"
        return self._call_mcp_skeleton(cmd, "analyze_voc", params)


class LocalModelVOCBackend(ToolBackend):
    backend_type = BackendType.LOCAL_MODEL

    def execute(self, params: dict) -> dict:
        raise ToolNotConfigured(
            "voc_analysis 本地模型后端未配置：接入本地 LLM/分类模型"
            "（如 easy-amazon-voc 本地权重）做评论情感与痛点聚类"
        )
