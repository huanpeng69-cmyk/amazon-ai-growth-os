"""Advertising Analysis Agent —— 执行器。"""
from __future__ import annotations

from app.agents.advertising.schemas import AdvertisingInput, AdvertisingOutput
from app.agents.advertising.tools import ADVERTISING_TOOLS


class AdvertisingAgent:
    name = "advertising"
    description = "PPC 增长分析：产品+站点 → 核心指标 + 可执行广告动作 + 预算建议"

    def run(self, inp: AdvertisingInput) -> AdvertisingOutput:
        analyze = next(t for t in ADVERTISING_TOOLS if t["name"] == "analyze_ads")["handler"]
        d = analyze(inp.product_name, inp.niche_keyword, inp.country,
                    inp.budget_usd, inp.current_acos)
        return AdvertisingOutput(**d)
