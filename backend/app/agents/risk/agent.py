"""Risk Agent —— 执行器。"""
from __future__ import annotations

from app.agents.risk.schemas import RiskInput, RiskItem, RiskOutput


class RiskAgent:
    name = "risk"
    description = "风险分析：利润率 / 广告依赖 / 回本 / 价格竞争 / 供应链 / 平台政策 多维风险评估"

    def run(self, inp: RiskInput) -> RiskOutput:
        m = inp.net_margin
        margin_sev = 90 if m < 0.05 else 70 if m < 0.10 else 45 if m < 0.18 else 20
        ad_sev = 80 if inp.ad_acos > 0.30 else 55 if inp.ad_acos > 0.20 else 30 if inp.ad_acos > 0.12 else 15
        pb = inp.payback_months
        payback_sev = 75 if (pb and pb > 24) else 50 if (pb and pb > 12) else 30 if (pb and pb > 6) else 12
        comp_sev = {"high": 60, "medium": 35, "low": 15}.get((inp.competition_level or "medium").lower(), 35)
        sc_sev = 20 if inp.supply_chain_connected else 55
        plat_sev = 30

        risks = [
            RiskItem(
                factor="利润率风险", severity=margin_sev,
                description=f"单件净利率 {m*100:.1f}%，安全垫{'极薄' if m < 0.10 else '偏薄' if m < 0.18 else '充足'}。",
                mitigation="通过供应链议价、优化包装与头程物流压降单件成本，或适度上调售价。",
            ),
            RiskItem(
                factor="广告依赖风险", severity=ad_sev,
                description=f"广告 ACOS {inp.ad_acos*100:.1f}%，{'过高侵蚀利润' if inp.ad_acos > 0.20 else '可控'}。",
                mitigation="打磨 Listing 转化率、清理无效关键词与否定词、逐步降低对付费流量的依赖。",
            ),
            RiskItem(
                factor="回本周期风险", severity=payback_sev,
                description=(f"预计回本 {pb:.1f} 个月。" if pb else "未设置首单投入，无回本压力。"),
                mitigation="采用小批量试单 + 分批补货，缩短现金占用与回本周期。",
            ),
            RiskItem(
                factor="价格竞争风险", severity=comp_sev,
                description=f"竞争强度 {inp.competition_level or '未知'}，同质化会压价。",
                mitigation="做差异化卖点 / 品牌化 / 捆绑组合，跳出纯价格战。",
            ),
            RiskItem(
                factor="供应链风险", severity=sc_sev,
                description="供应链接口未接通，成本与交期数据缺失，议价与断供风险不可见。" if not inp.supply_chain_connected
                else "供应链接口已接通，成本与交期可追踪。",
                mitigation="接入供应链数据接口（成本 / 交期 / 多源比价），建立安全库存与备选供应商。",
            ),
            RiskItem(
                factor="平台政策风险", severity=plat_sev,
                description="Amazon 政策变动、账号审核与类目合规存在不确定性。",
                mitigation="保持合规经营、分散站点与渠道、留存合规凭证。",
            ),
        ]

        # 加权综合（利润率与广告占主导）
        weights = {
            "利润率风险": 0.28, "广告依赖风险": 0.20, "回本周期风险": 0.17,
            "价格竞争风险": 0.15, "供应链风险": 0.12, "平台政策风险": 0.08,
        }
        score = sum(r.severity * weights.get(r.factor, 0.1) for r in risks)
        score = round(min(100.0, max(0.0, score)), 1)
        level = "high" if score >= 60 else "medium" if score >= 35 else "low"

        top = sorted(risks, key=lambda r: r.severity, reverse=True)[:2]
        warning = "主要风险：" + "；".join(f"{t.factor}（{t.severity:.0f}）" for t in top) + "。"

        return RiskOutput(risk_level=level, risk_score=score, risks=risks, warning_text=warning)
