"""Competitor Agent —— 执行器。"""
from __future__ import annotations

from app.agents.competitor.schemas import (
    CompetitorInput,
    CompetitorOutput,
    CompetitorProfile,
)
from app.agents.competitor.tools import COMPETITOR_TOOLS


class CompetitorAgent:
    name = "competitor"
    description = "竞品分析：利基关键词 → 头部竞品格局与差异化软肋"

    def run(self, inp: CompetitorInput) -> CompetitorOutput:
        scan = next(t for t in COMPETITOR_TOOLS if t["name"] == "scan_competitors")["handler"]
        res = scan(inp.niche_keyword, inp.country, inp.top_n)
        rows = res.get("profiles", [])
        summary = res.get("summary", "")

        competitors = [
            CompetitorProfile(
                name=r["name"], price_usd=r["price_usd"], avg_reviews=r["avg_reviews"],
                rating=r["rating"], est_market_share=r["est_market_share"], weakness=r["weakness"])
            for r in rows
        ]
        if not competitors:
            summary = summary or f"未能从 Amazon 检索到「{inp.niche_keyword}」的真实竞品数据。"
        return CompetitorOutput(
            niche_keyword=inp.niche_keyword, country=inp.country,
            competitors=competitors, summary=summary)
