"""Image Generation Agent —— 工具接口。

plan_images：调用 image_generation 工具获取原始图片方案，再叠加构图策略
（purpose / priority）与品牌一致性建议，形成可执行的拍摄/生成计划。
"""
from __future__ import annotations

from app.tools import ToolRegistry

# 每张图的用途与优先级（主图最高，依次讲故事）
_PURPOSES = ["主图", "使用场景", "卖点特写", "痛点对比", "尺寸规格", "生活方式"]


def plan_images(product_name: str, niche_keyword: str = "", style: str = "ecommerce",
                count: int = 6, platform: str = "amazon") -> dict:
    tool = ToolRegistry.get("image_generation")
    res = tool.run({
        "product_name": product_name,
        "niche_keyword": niche_keyword or product_name,
        "style": style,
        "count": count,
        "platform": platform,
    })
    raw = res.get("images", [])
    shots = []
    for i, img in enumerate(raw):
        purpose = _PURPOSES[i] if i < len(_PURPOSES) else f"附图{i+1}"
        shots.append({
            "scene": img.get("scene", purpose),
            "aspect_ratio": img.get("aspect_ratio", "1:1"),
            "prompt": img.get("prompt", ""),
            "description": img.get("description", ""),
            "purpose": purpose,
            "priority": i + 1,
        })

    readiness = round(min(100.0, 40 + 10 * len(shots)), 1)
    return {
        "product_name": product_name,
        "platform": platform,
        "shots": shots,
        "composition_strategy": (
            f"以白底 1:1 主图建立搜索点击，再用「{_PURPOSES[1]}→{_PURPOSES[2]}→"
            f"{_PURPOSES[3]}→{_PURPOSES[4]}→{_PURPOSES[5]}」顺序讲转化故事，"
            f"逐步打消价格、质量与适配顾虑。"
        ),
        "brand_guidance": (
            "保持统一色调与光线；首图不加文字/边框；附图一致的人物/场景风格以强化品牌记忆。"
        ),
        "readiness_score": readiness,
    }


IMAGE_TOOLS = [
    {
        "name": "plan_images",
        "description": "规划电商视觉：主图→场景→卖点→对比→规格→生活方式，含用途/优先级/构图策略。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "niche_keyword": {"type": "string"},
                "style": {"type": "string", "enum": ["ecommerce", "lifestyle", "minimal"]},
                "count": {"type": "integer", "default": 6},
                "platform": {"type": "string", "default": "amazon"},
            },
            "required": ["product_name"],
        },
        "handler": plan_images,
    },
]
