"""Image Generation Agent —— 执行器。"""
from __future__ import annotations

from app.agents.image.schemas import ImageGenAgentInput, ImageGenAgentOutput
from app.agents.image.tools import IMAGE_TOOLS


class ImageAgent:
    name = "image"
    description = "电商视觉策划：产品+利基 → 主图到附图的生成方案 + 构图策略"

    def run(self, inp: ImageGenAgentInput) -> ImageGenAgentOutput:
        plan = next(t for t in IMAGE_TOOLS if t["name"] == "plan_images")["handler"]
        d = plan(inp.product_name, inp.niche_keyword, inp.style, inp.count, inp.platform)
        return ImageGenAgentOutput(**d)
