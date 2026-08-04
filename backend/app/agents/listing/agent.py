"""Listing Agent —— 执行器。"""
from __future__ import annotations

from app.agents.listing.schemas import ListingInput, ListingOutput
from app.agents.listing.tools import LISTING_TOOLS


class ListingAgent:
    name = "listing"
    description = "高转化 Listing 文案：产品+利基+卖点 → 标题/五点/详情/关键词（商品图由视觉工厂独立生成）"

    def run(self, inp: ListingInput) -> ListingOutput:
        gen = next(t for t in LISTING_TOOLS if t["name"] == "generate_listing")["handler"]
        base = gen(inp.product_name, inp.niche_keyword, inp.key_features, inp.tone,
                   inp.target_country, inp.language)

        # 商品图生成已移至视觉工厂（#/visual），Listing 仅负责文案
        return ListingOutput(
            product_name=base["product_name"],
            tone=base["tone"],
            title=base["title"],
            bullet_points=base["bullet_points"],
            description=base["description"],
            search_terms=base["search_terms"],
            image_plan=[],  # 商品图由视觉工厂（#/visual）独立生成
            compliance_notes=base["compliance_notes"],
            completeness_score=base["completeness_score"],
        )
