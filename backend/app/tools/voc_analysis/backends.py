"""voc_analysis 后端适配器。

- VOCBackend：经统一数据层（review_connector）获取真实评论，抽取并排序用户痛点。
- McpBackend：未来接入 easy-amazon-voc MCP（真实评论爬取+聚类）。
- LocalModelBackend：未来接入本地 LLM/分类模型做评论情感与痛点归类。
"""
from __future__ import annotations

from app.database import SessionLocal
from app.data import dal
from app.tools.base import BackendType, ToolBackend, ToolNotConfigured

# 痛点 → 改进建议（轻量映射；真实场景由 VOC 模型产出）
_FIX_MAP: dict[str, str] = {
    "材质": "升级为食品级/更耐用材质，并在 Listing 前置说明材质认证。",
    "噪音": "采用静音结构/减震设计，标注噪音分贝值。",
    "电池": "提升电池容量与循环寿命，提供快充方案。",
    "漏水": "重新设计密封结构，增加防漏测试与质保承诺。",
    "安装": "简化安装步骤，附图文/视频说明书。",
    "尺寸": "明确标注尺寸对照表，提供多种规格可选。",
    "气味": "采用无异味环保材料，出厂前通风处理。",
    "清洁": "采用可拆卸/ dishwasher-safe 设计。",
}


def _suggest_fix(pain: str) -> str:
    for key, fix in _FIX_MAP.items():
        if key in pain:
            return fix
    return f"针对「{pain}」做差异化卖点与品质升级，并在 Listing 中前置说明。"


class VOCBackend(ToolBackend):
    backend_type = BackendType.MOCK  # 配置键仍为 mock；数据已改为真实 Connector 来源

    def execute(self, params: dict) -> dict:
        db = SessionLocal()
        try:
            products = dal.list_products(db, keyword=params["niche_keyword"], country=params["country"])
        finally:
            db.close()
        asin = products[0].asin if products else None

        reviews = []
        if asin:
            db2 = SessionLocal()
            try:
                reviews = dal.get_reviews(db2, asin=asin, country=params["country"])
            finally:
                db2.close()

        counter: dict[str, int] = {}
        for r in reviews:
            for pk in r.pain_keywords:
                counter[pk] = counter.get(pk, 0) + 1

        top_n = params.get("top_n", 5)
        ranked = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
        pains = [
            {
                "pain": k,
                "severity": min(100, 45 + v * 5),
                "evidence": v,
                "suggested_fix": _suggest_fix(k),
            }
            for k, v in ranked
        ]
        if pains:
            head = pains[0]
            summary = (
                f"对「{params['niche_keyword']}」的 {len(pains)} 条主要用户痛点分析："
                f"核心痛点「{head['pain']}」（严重度 {head['severity']}，证据量 {head['evidence']}），"
                f"建议{head['suggested_fix']}"
            )
        else:
            summary = f"未从「{params['niche_keyword']}」提取到显著用户痛点。"
        return {
            "niche_keyword": params["niche_keyword"],
            "country": params["country"],
            "pain_points": pains,
            "summary": summary,
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
