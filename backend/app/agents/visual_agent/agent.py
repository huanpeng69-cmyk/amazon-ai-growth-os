"""Product Visual Agent —— 执行器（策略优先管线）。

流程：视觉策略 → 7 图规划 → 调用 image_generation 工具产出基础生成结果
→ 质量评分 → 优化建议。绝不跳过策略直接出图。
"""
from __future__ import annotations

from app.agents.visual_agent.schemas import (
    ImageSlot,
    VisualAgentInput,
    VisualAgentOutput,
    VisualStrategy,
)
from app.agents.visual_agent.tools import VISUAL_TOOLS


def _h(name: str):
    return next(t for t in VISUAL_TOOLS if t["name"] == name)["handler"]


class VisualAgent:
    name = "visual"
    description = "策略优先的电商视觉：定位+VOC+竞品 → 视觉策略 → 7图规划 + Prompt + 生成请求 + 质量评分"

    def run(self, inp: VisualAgentInput) -> VisualAgentOutput:
        # 1) 视觉策略
        strat = _h("generate_visual_strategy")(
            inp.product_name, inp.niche_keyword, inp.market_positioning,
            inp.voc_pain_points, inp.competitor_insights, inp.country)

        # 2) 7 图规划
        plan = _h("plan_listing_images")(
            strat, inp.product_name, inp.niche_keyword, inp.voc_pain_points,
            inp.competitor_insights, inp.style, inp.country)

        # 3) 调用 image_generation 工具产出基础生成结果，合并到规划
        #    把每张规划好的差异化 Prompt 传给生图后端，保证『展示 Prompt = 真实生图 Prompt』
        plan_prompts = [p.get("generation_prompt", "") for p in plan]
        scenes = _h("generate_images_via_tool")(
            inp.product_name, inp.niche_keyword, inp.style, 7, "amazon", plan_prompts)
        for i, slot in enumerate(plan):
            sc = scenes[i] if i < len(scenes) else {}
            slot["generated_scene"] = sc.get("scene", slot["purpose"])
            slot["generated_description"] = sc.get("description", "")
            slot["image_url"] = sc.get("image_url")  # 真实图片 URL（WisArt 生图）或 None
            # 用后端实际拿去生图的 Prompt 覆盖展示，确保前后一致、每张不同
            if sc.get("prompt"):
                slot["generation_prompt"] = sc["prompt"]

        # 4) 质量评分
        quality = _h("score_image_quality")(plan, inp.voc_pain_points)

        # 5) 优化建议
        suggestions = __import__(
            "app.agents.visual_agent.tools", fromlist=["build_optimization_suggestions"]
        ).build_optimization_suggestions(plan, quality, inp.voc_pain_points, inp.competitor_insights)

        composition = (
            f"以「{strat['main_image_strategy'][:24]}…」为主图方向，"
            f"7 张图按 主图→卖点→场景→痛点对比→规格→生活方式→信任背书 顺序讲转化故事，"
            f"色彩统一「{strat['color_direction']}」，痛点映射到第 {3}、{2} 张。"
        )

        return VisualAgentOutput(
            product_name=inp.product_name,
            strategy=VisualStrategy(**strat),
            image_plan=[ImageSlot(**p) for p in plan],
            quality_score=quality,
            optimization_suggestions=suggestions,
            composition_strategy=composition,
        )
