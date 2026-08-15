"""Product Agent —— 执行器。

基于实时 Bright Data + 真实评论得到的评分，由大模型生成"机会理由"与"差异化定位"，
不再使用硬编码 f-string 模板。大模型不可用时退化为基于真实评分的客观陈述。
"""
from __future__ import annotations

from app.agents.product.schemas import ProductInput, ProductOutput
from app.agents.product.tools import PRODUCT_TOOLS
from app.agents._util import llm_available, synthesize
from app.llm.agnes import AgnesError

_SYSTEM = (
    "你是亚马逊选品顾问。只依据提供的真实评分数据，用中文给出客观的机会判断与定位建议，"
    "绝不编造任何数据或产品事实。"
)


def _verdict(score: float) -> str:
    if score >= 75:
        return "强烈推荐"
    if score >= 60:
        return "推荐"
    if score >= 45:
        return "谨慎进入（需差异化）"
    return "不推荐"


def _narrative(s: dict, niche: str, country: str):
    """调用大模型基于真实评分生成 reasons + positioning。失败返回 None。"""
    if not llm_available():
        return None
    prompt = (
        f"利基「{niche}」（站点 {country}）的真实评分如下：\n"
        f"- 机会分 {s['opportunity_score']}/100\n"
        f"- 需求强度 {s['demand_score']}/100，月规模约 ${s['market_size_monthly_usd']:,}"
        f"（年增速 {s['growth_yoy']*100:.0f}%)\n"
        f"- 竞争程度 {s['competition_level']}（蓝海分 {s['competition_score']}/100）\n"
        f"- 痛点强度 {s['pain_severity_score']}/100，核心痛点「{s['top_pain']}」\n"
        f"- 预算适配 {s['budget_fit_score']}/100\n\n"
        "请基于以上真实数据输出 JSON：\n"
        "{\"reasons\": [3-4 条中文要点，每条说明一个维度的真实含义与机会/风险], "
        "\"positioning\": \"一句话差异化定位建议（中文，结合核心痛点与竞争度）\"}"
    )
    try:
        d = synthesize(_SYSTEM, prompt, temperature=0.3, max_tokens=700)
    except AgnesError:
        return None
    reasons = [str(r) for r in (d.get("reasons") or []) if str(r).strip()][:4]
    positioning = (d.get("positioning") or "").strip()
    if reasons and positioning:
        return reasons, positioning
    return None


class ProductAgent:
    name = "product"
    description = "产品机会判断：利基 + 预算 → 是否值得做 + 推荐定位（真实评分 + 大模型解读）"

    def run(self, inp: ProductInput) -> ProductOutput:
        score = next(t for t in PRODUCT_TOOLS if t["name"] == "score_opportunity")["handler"]
        s = score(inp.niche_keyword, inp.country, inp.budget_usd)

        verdict = _verdict(s["opportunity_score"])
        narr = _narrative(s, inp.niche_keyword, inp.country)
        if narr:
            reasons, positioning = narr
        else:
            reasons = [
                f"需求强度 {s['demand_score']}/100，月规模约 ${s['market_size_monthly_usd']:,}（增速 {s['growth_yoy']*100:.0f}%）",
                f"竞争程度 {s['competition_level']}（蓝海分 {s['competition_score']}/100）",
                f"痛点强度 {s['pain_severity_score']}/100，核心痛点「{s['top_pain']}」",
                f"预算适配 {s['budget_fit_score']}/100（预算 ${inp.budget_usd:,}）",
            ]
            positioning = (
                f"以「解决 {s['top_pain']}」为核心差异化卖点切入 {inp.niche_keyword} 利基，"
                f"主打 {s['competition_level']} 竞争蓝海。"
            )
        return ProductOutput(
            niche_keyword=s["niche_keyword"], verdict=verdict,
            opportunity_score=s["opportunity_score"], reasons=reasons,
            recommended_positioning=positioning)
