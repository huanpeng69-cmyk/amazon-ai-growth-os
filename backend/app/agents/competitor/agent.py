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
        rows = scan(inp.niche_keyword, inp.country, inp.top_n)

        competitors = [
            CompetitorProfile(
                name=r["name"], price_usd=r["price_usd"], avg_reviews=r["avg_reviews"],
                rating=r["rating"], est_market_share=r["est_market_share"], weakness=r["weakness"])
            for r in rows
        ]
        top = competitors[0]
        summary = (f"「{inp.niche_keyword}」头部由 {len(competitors)} 个主要卖家占据，"
                   f"榜首 {top.name} 约 {top.est_market_share*100:.0f}% 份额、评分 {top.rating}、"
                   f"评论 {top.avg_reviews:,}。共性软肋为「{top.weakness}」，"
                   f"可作为差异化切入方向。")
        return CompetitorOutput(
            niche_keyword=inp.niche_keyword, country=inp.country,
            competitors=competitors, summary=summary)
