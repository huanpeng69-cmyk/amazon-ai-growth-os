"""Product Visual Agent —— 工具接口（策略优先的视觉生成管线）。

四件套工具：
- generate_visual_strategy：综合定位/VOC/竞品推理视觉策略。
- plan_listing_images：基于策略规划 7 张 Listing 图片（含 Prompt/请求/质量检查）。
- generate_images_via_tool：调用 image_generation 工具产出基础生成结果。
- score_image_quality：评估整体视觉质量 0-100。
"""
from __future__ import annotations

import hashlib

from app.tools import ToolRegistry
from app.llm.agnes import agnes as _agnes

# 7 张 Listing 图片的标准槽位：(slot, purpose, aspect_ratio)
SLOTS = [
    ("主图", "主图白底", "1:1"),
    ("附图1", "卖点特写", "1:1"),
    ("附图2", "使用场景", "1:1"),
    ("附图3", "痛点对比", "1:1"),
    ("附图4", "尺寸规格", "1:1"),
    ("附图5", "生活方式", "1:1"),
    ("附图6", "信任背书", "1:1"),
]


def _pain_to_angle(pain: str) -> str:
    p = (pain or "").lower()
    if any(k in p for k in ["静音", "噪音", "吵", "声"]):
        return "静音电机特写 + 分贝对比图标"
    if any(k in p for k in ["材质", "安全", "食品级", "有害", "无毒", "生锈"]):
        return "食品级/安全材质认证标识特写"
    if any(k in p for k in ["清洗", "清洁", "拆洗", "死角"]):
        return "可拆洗结构一拆即净演示"
    if any(k in p for k in ["容量", "续航", "大", "小", "不足"]):
        return "容量/续航刻度对比"
    if any(k in p for k in ["漏水", "防水", "潮湿", "进水"]):
        return "防水/防漏结构演示"
    if any(k in p for k in ["打滑", "松动", "断裂", "易坏", "不耐用"]):
        return "加固/耐用结构特写"
    return f"针对「{pain}」的前后对比演示"


def _color_direction(product_name: str, niche_keyword: str) -> str:
    h = int(hashlib.md5((product_name + niche_keyword).lower().encode("utf-8")).hexdigest(), 16)
    palettes = [
        "清新蓝绿：aquamarine + soft blue，传递洁净/健康",
        "暖橙活力：warm orange + cream，传递活力/亲和",
        "极简黑白：minimal black/white + 单色点缀，传递高端",
        "自然森绿：forest green + wood tone，传递环保/自然",
        "科技靛蓝：indigo + cyan glow，传递科技/精准",
    ]
    return palettes[h % len(palettes)]


def _parse_json_block(text: str) -> dict:
    """从 LLM 输出中稳健提取 JSON 对象（兼容 ```json 围栏与前后多余文本）。"""
    import json as _json
    import re as _re
    t = (text or "").strip()
    m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if m:
        t = m.group(1).strip()
    s, e = t.find("{"), t.rfind("}")
    if s != -1 and e != -1:
        t = t[s:e + 1]
    return _json.loads(t)


def _strategy_via_agnes(product_name: str, niche_keyword: str, market_positioning: str,
                        voc_pain_points: list, competitor_insights: str, country: str) -> dict:
    """调用 Agnes AI（OpenAI 兼容）真实生成视觉策略。任何异常都抛出，由上层回退启发式。"""
    pains = [p for p in (voc_pain_points or []) if p]
    pain_bullets = "\n".join(f"- {p}" for p in pains) or "（未提供）"
    user = (
        f"为以下 Amazon 产品生成「视觉策略」JSON，只输出严格 JSON，不要任何解释文字。\n"
        f"产品：{product_name}\n利基：{niche_keyword or '（未提供）'}\n"
        f"市场定位：{market_positioning or '（未提供）'}\n目标站点：{country}\n"
        f"VOC 痛点：\n{pain_bullets}\n竞品分析：{competitor_insights or '（无）'}\n\n"
        "JSON 字段：\n"
        "- main_image_strategy: 字符串，白底 1:1 主图的视觉策略，以最痛点为锚点。\n"
        "- visual_angles: 字符串数组（4-6 个），各附图应采用的视觉角度。\n"
        "- differentiation: 字符串，相对竞品的差异化视觉锚点。\n"
        "- emotional_hook: 字符串，情感钩子。\n"
        "- color_direction: 字符串，建议色彩方向（含具体色名/色值）。"
    )
    messages = [
        {"role": "system", "content": "你是资深 Amazon 电商视觉策略师，擅把定位/VOC/竞品转化为可执行图片策略。只输出严格 JSON。"},
        {"role": "user", "content": user},
    ]
    text = _agnes.chat(messages, temperature=0.6, max_tokens=1200)
    data = _parse_json_block(text)
    required = {"main_image_strategy", "visual_angles", "differentiation", "emotional_hook", "color_direction"}
    if not required.issubset(data.keys()):
        raise ValueError(f" Agnes 返回缺少字段: {required - data.keys()}")
    angles = data["visual_angles"]
    if isinstance(angles, str):
        angles = [angles]
    angles = [str(a) for a in angles][:6]
    return {
        "main_image_strategy": str(data["main_image_strategy"]),
        "visual_angles": angles,
        "differentiation": str(data["differentiation"]),
        "emotional_hook": str(data["emotional_hook"]),
        "color_direction": str(data["color_direction"]),
    }


def generate_visual_strategy(product_name: str, niche_keyword: str = "", market_positioning: str = "",
                             voc_pain_points: list | None = None, competitor_insights: str = "",
                             country: str = "US") -> dict:
    """视觉策略入口：优先调用 Agnes AI 真实文本模型；未配置或失败时回退启发式。"""
    if _agnes.enabled():
        try:
            return _strategy_via_agnes(product_name, niche_keyword, market_positioning,
                                       voc_pain_points, competitor_insights, country)
        except Exception as e:  # 真实 LLM 异常 → 回退，保证始终可用
            import logging
            logging.getLogger("visual_agent").warning("Agnes 视觉策略生成失败，回退启发式: %s", e)
    return _heuristic_strategy(product_name, niche_keyword, market_positioning,
                               voc_pain_points, competitor_insights, country)


def _heuristic_strategy(product_name: str, niche_keyword: str = "", market_positioning: str = "",
                        voc_pain_points: list | None = None, competitor_insights: str = "",
                        country: str = "US") -> dict:
    pains = [p for p in (voc_pain_points or []) if p]
    top_pain = pains[0] if pains else "用户未被满足的核心需求"
    positioning = market_positioning or f"面向 {niche_keyword or product_name} 的高品质选择"

    angles = [_pain_to_angle(p) for p in pains[:4]]
    angles += ["产品全貌白底展示", "真实使用场景代入", "品牌信任背书"]
    seen: set[str] = set()
    angles = [a for a in angles if not (a in seen or seen.add(a))]

    comp_brief = competitor_insights.strip()
    if len(comp_brief) > 80:
        comp_brief = comp_brief[:80] + "…"
    if not comp_brief:
        comp_brief = "头部卖家同质化、缺情感连接"

    main = (f"白底 1:1 主图：居中高清展示 {product_name}，以「{top_pain}」为视觉锚点；"
            f"前 80px 信息区突出「{niche_keyword or product_name}」核心流量词，"
            f"靠高对比与单一卖点图标提升 CTR，禁止文字堆砌与边框。")
    diff = (f"对比竞品：{comp_brief}。用「{top_pain}」的解决视觉作为差异锚点，"
            f"竞品未强调处即我方主视觉。")
    hook = f"情感钩子：围绕「{positioning}」建立安心/省心联想，让买家一眼看到「解决了我的烦恼」。"
    color = _color_direction(product_name, niche_keyword)

    return {
        "main_image_strategy": main,
        "visual_angles": angles[:6],
        "differentiation": diff,
        "emotional_hook": hook,
        "color_direction": color,
    }


def _slot_spec(slot: str, purpose: str, product_name: str, niche: str, top_pain: str,
               sec_pain: str, competitor_insights: str, strategy: dict):
    color = strategy.get("color_direction", "")
    # 色彩方向融入 Prompt：非空时以 ", 色彩" 形式插入，避免空值产生双逗号
    color_part = f", {color}" if color else ""
    base = f"Professional Amazon product photography of {product_name}, {niche} niche"

    if slot == "主图":
        concept = f"白底高清主图，居中展示 {product_name}，单一视觉焦点"
        diff = f"用「{top_pain}」解决视觉作主图差异锚点（竞品多用平铺）"
        pain = top_pain
        prompt = (f"{base}, pure white background RGB 255, product centered, 85% frame fill, "
                  f"studio softbox lighting, ultra sharp{color_part}, no text no border, ecommerce hero shot")
        checks = ["纯白背景 RGB 255,255,255", "产品占比 ≥ 85%", "无文字/水印/边框",
                  "分辨率 ≥ 1600px", "单一视觉焦点"]
    elif slot == "附图1":  # 卖点特写
        concept = f"放大核心卖点细节，呼应「{top_pain}」"
        diff = "竞品只拍全景，我方用微距特写强化材质/工艺"
        pain = top_pain
        prompt = (f"{base}, extreme macro close-up of key feature solving {top_pain}, shallow depth of field, "
                  f"detail texture{color_part}, studio lighting, infographic-ready negative space")
        checks = ["微距清晰无噪点", "保留信息图留白", "光影突出材质质感", "比例 1:1"]
    elif slot == "附图2":  # 使用场景
        concept = f"真实场景中 {product_name} 的使用瞬间"
        diff = "场景代入感优于竞品白底堆砌"
        pain = sec_pain
        prompt = (f"{base}, real-life usage scene, natural light, lifestyle context, hands interacting, "
                  f"{color}, authentic mood")
        checks = ["场景真实自然", "产品清晰可辨", "光线符合场景", "人物/手部自然"]
    elif slot == "附图3":  # 痛点对比
        concept = f"使用前后对比，直击「{top_pain}」"
        diff = "竞品回避痛点，我方用对比直击购买动机"
        pain = top_pain
        prompt = (f"{base}, before and after split comparison, clear visual contrast solving {top_pain}, "
                  f"{color}, clean layout, before on left after on right")
        checks = ["左右对比清晰", "痛点-解决逻辑直观", "无夸大宣传词", "比例 1:1"]
    elif slot == "附图4":  # 尺寸规格
        concept = "尺寸对照 + 规格参数信息图"
        diff = "用常见物参照降低购买犹豫（竞品仅给数字）"
        pain = None
        prompt = (f"{base}, size comparison infographic with common object reference, dimension callouts, "
                  f"clean white background{color_part}, technical clarity")
        checks = ["尺寸标注准确", "参照物易懂", "信息层级清晰", "无错别字"]
    elif slot == "附图5":  # 生活方式
        hook = strategy.get("emotional_hook", "")[:24]
        concept = f"品牌调性生活方式图，强化「{hook}」"
        diff = "传递品牌情感，竞品缺情感连接"
        pain = None
        prompt = (f"{base}, premium lifestyle scene, brand mood, aspirational setting{color_part}, "
                  f"cinematic lighting, shallow depth of field")
        checks = ["品牌调性统一", "情感氛围到位", "产品自然融入", "不喧宾夺主"]
    else:  # 附图6 信任背书
        concept = "评分/认证/与竞品对比优势，建立信任"
        diff = "直接对比竞品劣势，强化购买信心"
        pain = None
        prompt = (f"{base}, trust badge composition, rating stars, certification icons, "
                  f"comparison chart vs competitors{color_part}, professional layout")
        checks = ["认证/评分真实可核", "对比图表客观", "无贬低竞品措辞", "比例 1:1"]
    return concept, diff, pain, prompt, checks


def plan_listing_images(strategy: dict, product_name: str, niche_keyword: str = "",
                        voc_pain_points: list | None = None, competitor_insights: str = "",
                        style: str = "ecommerce", country: str = "US") -> list[dict]:
    pains = [p for p in (voc_pain_points or []) if p]
    top_pain = pains[0] if pains else "用户未被满足的核心需求"
    sec_pain = pains[1] if len(pains) > 1 else top_pain
    niche = niche_keyword or product_name

    plan: list[dict] = []
    for slot, purpose, ar in SLOTS:
        concept, diff, pain, prompt, checks = _slot_spec(
            slot, purpose, product_name, niche, top_pain, sec_pain, competitor_insights, strategy)
        req = {
            "tool": "image_generation",
            "input": {
                "product_name": product_name,
                "niche_keyword": niche,
                "style": style,
                "count": 1,
                "platform": "amazon",
                "scene_hint": purpose,
            },
        }
        plan.append({
            "slot": slot, "purpose": purpose, "concept": concept,
            "differentiation_point": diff, "pain_addressed": pain,
            "aspect_ratio": ar, "generation_prompt": prompt,
            "quality_checks": checks, "generation_request": req,
        })
    return plan


def generate_images_via_tool(product_name: str, niche_keyword: str = "", style: str = "ecommerce",
                             count: int = 7, platform: str = "amazon",
                             prompts: list[str] | None = None) -> list[dict]:
    """调用 image_generation 工具产出基础生成结果。

    prompts：可选，逐张文生图 Prompt（与 count 对齐）。传入后生图即使用这些
    差异化 Prompt，保证『前端展示的 Prompt』与『真实生图 Prompt』完全一致。
    """
    tool = ToolRegistry.get("image_generation")
    res = tool.run({
        "product_name": product_name,
        "niche_keyword": niche_keyword or product_name,
        "style": style,
        "count": count,
        "platform": platform,
        "prompts": prompts or [],
    })
    return res.get("images", [])


def score_image_quality(image_plan: list[dict], voc_pain_points: list | None = None) -> float:
    n = max(1, len(image_plan))
    coverage = len(image_plan) / 7 * 40
    addressing = sum(1 for s in image_plan if s.get("pain_addressed")) / n * 30
    diff = 15.0 if any(s.get("differentiation_point") for s in image_plan) else 6.0
    avg_len = sum(len(s.get("generation_prompt", "")) for s in image_plan) / n
    spec = min(15.0, avg_len / 12.0)
    total = round(coverage + addressing + diff + spec, 1)
    return max(0.0, min(100.0, total))


def build_optimization_suggestions(image_plan: list[dict], quality: float,
                                   voc_pain_points: list | None, competitor_insights: str) -> list[str]:
    pains = [p for p in (voc_pain_points or []) if p]
    addressing = sum(1 for s in image_plan if s.get("pain_addressed"))
    s: list[str] = []
    if pains and addressing < 2:
        s.append("痛点覆盖不足：至少 2 张图直接呼应 TOP 痛点（建议强化痛点对比图与卖点特写图）。")
    if not competitor_insights.strip():
        s.append("未提供竞品分析：补充竞品洞察可让差异锚点更精准。")
    if quality < 70:
        s.append("整体视觉质量偏低：补充场景图与信任背书图，并细化每张 Prompt 的光影与材质描述。")
    s.append("主图建议做 A/B 测试：白底纯净版 vs 含单一卖点图标版，按 CTR 取胜。")
    s.append("A+ 内容追加 1 张对比视频缩略图 + 规格表，提升转化与停留。")
    return s


VISUAL_TOOLS = [
    {
        "name": "generate_visual_strategy",
        "description": "综合定位/VOC痛点/竞品分析推理视觉策略（主图策略/角度/差异/情感/色彩）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "niche_keyword": {"type": "string"},
                "market_positioning": {"type": "string"},
                "voc_pain_points": {"type": "array", "items": {"type": "string"}},
                "competitor_insights": {"type": "string"},
                "country": {"type": "string"},
            },
            "required": ["product_name"],
        },
        "handler": generate_visual_strategy,
    },
    {
        "name": "plan_listing_images",
        "description": "基于策略规划 7 张 Listing 图片（主图+6附图），含创意/Prompt/请求/质量检查。",
        "input_schema": {
            "type": "object",
            "properties": {
                "strategy": {"type": "object"},
                "product_name": {"type": "string"},
                "niche_keyword": {"type": "string"},
                "voc_pain_points": {"type": "array", "items": {"type": "string"}},
                "competitor_insights": {"type": "string"},
                "style": {"type": "string"},
            },
            "required": ["strategy", "product_name"],
        },
        "handler": plan_listing_images,
    },
    {
        "name": "generate_images_via_tool",
        "description": "调用 image_generation 工具产出基础生成结果（场景+描述）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "niche_keyword": {"type": "string"},
                "style": {"type": "string"},
                "count": {"type": "integer", "default": 7},
            },
            "required": ["product_name"],
        },
        "handler": generate_images_via_tool,
    },
    {
        "name": "score_image_quality",
        "description": "评估 7 张图片规划的整体视觉质量 0-100（覆盖/痛点/差异/Prompt 细节）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_plan": {"type": "array"},
                "voc_pain_points": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["image_plan"],
        },
        "handler": score_image_quality,
    },
]
