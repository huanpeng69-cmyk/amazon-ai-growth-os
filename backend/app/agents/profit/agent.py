"""Profit Agent —— 执行器（确定性计算，不依赖 LLM）。"""
from __future__ import annotations

from app.agents.profit.schemas import ProfitBreakdown, ProfitInput, ProfitOutput


def _margin_score(margin: float) -> float:
    """净利率 → 基础评分（0-100）。"""
    if margin <= 0:
        return 0.0
    if margin >= 0.30:
        return 88.0
    if margin >= 0.20:
        return 70.0 + (margin - 0.20) / 0.10 * 18.0
    if margin >= 0.10:
        return 50.0 + (margin - 0.10) / 0.10 * 20.0
    if margin >= 0.05:
        return 35.0 + (margin - 0.05) / 0.05 * 15.0
    return 35.0 * (margin / 0.05)


class ProfitAgent:
    name = "profit"
    description = "产品利润测算：售价 + 成本 + 物流 + Amazon 费用 + 广告 → 毛利润 / 净利润 / 利润率 / 盈利评分 / 投资建议"

    def run(self, inp: ProfitInput) -> ProfitOutput:
        p = inp.selling_price
        referral_fee = round(p * inp.referral_fee_rate, 4)
        fba_fee = inp.fba_fee
        amazon_fee = round(referral_fee + fba_fee, 4)
        ad_cost = round(p * inp.ad_acos, 4)
        other = inp.other_cost_per_unit

        gross = round(p - inp.product_cost - inp.shipping_cost - amazon_fee, 4)
        net = round(gross - ad_cost - other, 4)
        margin = round(net / p, 4) if p else 0.0

        per_unit = ProfitBreakdown(
            selling_price=p, product_cost=inp.product_cost, shipping_cost=inp.shipping_cost,
            referral_fee=referral_fee, fba_fee=fba_fee, amazon_fee=amazon_fee,
            ad_cost=ad_cost, other_cost=other, gross_profit=gross, net_profit=net, net_margin=margin,
        )

        # 销量取用户提供值（由 router 在调用前解析）；此处只是兜底
        units = inp.monthly_units or 0
        monthly_gross = round(gross * units, 2)
        monthly_net = round(net * units, 2)
        monthly_op = round(monthly_net - inp.monthly_fixed_cost, 2)

        score = _margin_score(margin)

        rec, reason = self._recommend(margin, score)

        return ProfitOutput(
            product_name=inp.product_name, country=inp.country,
            per_unit=per_unit, monthly_units=units,
            monthly_gross_profit=monthly_gross, monthly_net_profit=monthly_net,
            monthly_fixed_cost=inp.monthly_fixed_cost, monthly_net_operating=monthly_op,
            profitability_score=round(score, 1),
            recommendation=rec, recommendation_reason=reason,
            cost_source=inp.cost_source or "manual",
        )

    @staticmethod
    def _recommend(margin: float, score: float):
        if margin >= 0.18:
            return "invest", (
                f"单件净利率 {margin*100:.1f}%，盈利质量较好，建议投入。"
                "建议先小批量验证转化，再逐步加大广告与备货。"
            )
        if margin >= 0.08:
            return "cautious", (
                f"单件净利率 {margin*100:.1f}%，处于可运营区间但安全垫偏薄。"
                "建议压降产品/物流成本或优化广告 ACOS 后再放量，控制首单规模。"
            )
        if margin > 0:
            return "avoid", (
                f"单件净利率仅 {margin*100:.1f}%，容错空间极小，任一环节波动即亏损。"
                "建议重新议价供应链或上调售价，否则不建议投入。"
            )
        return "avoid", (
            "按当前结构单件已亏损，必须下调成本或提高售价后才能考虑投入。"
        )
