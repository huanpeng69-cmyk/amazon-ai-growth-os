"""Product Agent —— 执行器。"""
from __future__ import annotations

from app.agents.product.schemas import ProductInput, ProductOutput
from app.agents.product.tools import PRODUCT_TOOLS


def _verdict(score: float) -> str:
    if score >= 75:
        return "强烈推荐"
    if score >= 60:
        return "推荐"
    if score >= 45:
        return "谨慎进入（需差异化）"
    return "不推荐"


class ProductAgent:
    name = "product"
    description = "产品机会判断：利基 + 预算 → 是否值得做 + 推荐定位"

    def run(self, inp: ProductInput) -> ProductOutput:
        score = next(t for t in PRODUCT_TOOLS if t["name"] == "score_opportunity")["handler"]
        s = score(inp.niche_keyword, inp.country, inp.budget_usd)

        verdict = _verdict(s["opportunity_score"])
        reasons = [
            f"需求强度 {s['demand_score']}/100，月规模约 ${s['market_size_monthly_usd']:,}（增速 {s['growth_yoy']*100:.0f}%）",
            f"竞争程度 {s['competition_level']}（蓝海分 {s['competition_score']}/100）",
            f"痛点强度 {s['pain_severity_score']}/100，核心痛点「{s['top_pain']}」",
            f"预算适配 {s['budget_fit_score']}/100（预算 ${inp.budget_usd:,}）",
        ]
        positioning = (f"以「解决 {s['top_pain']}」为核心差异化卖点切入 "
                       f"{inp.niche_keyword} 利基，主打 {s['competition_level']} 竞争蓝海。")
        return ProductOutput(
            niche_keyword=s["niche_keyword"], verdict=verdict,
            opportunity_score=s["opportunity_score"], reasons=reasons,
            recommended_positioning=positioning)
