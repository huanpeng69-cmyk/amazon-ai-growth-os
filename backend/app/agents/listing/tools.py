"""Listing Agent —— 工具接口（Tool Interface）。

- generate_listing：文案引擎。优先调用 Agnes AI 生成地道英文 Listing（输入可为中文，
  自动翻译为母语级英文）；未配置或失败时回退确定性英文模板，保证欧美站点开箱即用。
- build_image_plan：调用 image_generation 工具，给出主图到附图的生成方案。
"""
from __future__ import annotations

import json
import logging
import re

from app.tools import ToolRegistry
from app.tools.i18n import cn_to_en, has_cjk
from app.llm.agnes import agnes as _agnes

logger = logging.getLogger("listing")

TONE_MODIFIER = {
    "专业可信": "Professional",
    "年轻活力": "Vibrant",
    "高端奢华": "Premium",
}
_REV_TONE = {v.lower(): v for v in TONE_MODIFIER.values()}


def _tone_en(tone: str) -> str:
    if not tone:
        return "Professional"
    if tone in TONE_MODIFIER:
        return TONE_MODIFIER[tone]
    if tone.lower() in _REV_TONE:
        return _REV_TONE[tone.lower()]
    return tone


# —— 确定性英文模板（兜底，无 LLM 也可用） ——
_BULLET_EN = [
    "{name} is built around {f}, directly targeting the core pain point in the '{niche}' scenario so daily use is easier and more efficient.",
    "Unlike ordinary options, the {f} of {name} delivers a noticeable upgrade—cutting returns and negative reviews.",
    "With {f}, {name} balances function and finish, making it just as fitting for gifting as for personal use.",
    "Refined from real '{niche}' feedback, {name}'s {f} lowers the learning curve for first-time users.",
    "{name} pairs {f} with worry-free after-sales, so you buy with confidence and use it for the long run.",
]

_DESCRIPTION_EN = (
    "About {name}:\n"
    "We focus on the real pain points behind '{niche}'. {name} combines {feat_line} with a {tone_en} overall tone, "
    "balancing function and finish.\n\n"
    "Why choose {name}:\n"
    "• User-driven {feat_line} design that consistently meets your expectations for '{niche}'.\n"
    "• Materials and workmanship built to last, lowering hidden long-term costs.\n"
    "• Ideal for daily and high-frequency use—whether for yourself, as a gift, or for resale.\n\n"
    "Add {name} to your cart and start a smoother '{niche}' experience today."
)


def _title(product_name: str, features: list[str], niche: str, tone: str) -> str:
    """标题 ≤ 200 字符：核心流量词 + 最大卖点 + 利基 + 站点词（英文脚手架）。"""
    tone_en = _tone_en(tone)
    lead = features[0] if features else (niche or "Essential")
    bits = [product_name, lead, tone_en]
    if niche and niche.lower() not in product_name.lower() and niche != lead:
        bits.append(niche)
    bits += ["Pet Supplies" if "pet" in (niche + product_name).lower() else "Home Essentials"]
    seen = set()
    clean = []
    for b in bits:
        if b and b.lower() not in seen:
            seen.add(b.lower())
            clean.append(b)
    title = " - ".join(clean)
    if len(title) > 200:
        title = title[:197].rstrip() + "..."
    return title


def _bullets(product_name: str, features: list[str], niche: str) -> list[str]:
    """五点描述（英文）：每条一个利益点，绑定卖点/痛点。"""
    if not features:
        features = [niche or "durable design", "easy to use", "premium quality",
                    "great value", "risk-free guarantee"]
    out = []
    for i, f in enumerate(features[:5]):
        out.append(_BULLET_EN[i % len(_BULLET_EN)].format(f=f, name=product_name, niche=niche or "daily use"))
    return out


def _description(product_name: str, features: list[str], niche: str, tone: str) -> str:
    feat_line = ", ".join(features) if features else (niche or "durable design")
    return _DESCRIPTION_EN.format(name=product_name, niche=niche or "daily use",
                                  feat_line=feat_line, tone_en=_tone_en(tone))


def _search_terms(product_name: str, features: list[str], niche: str) -> list[str]:
    base = [product_name, niche] if niche else [product_name]
    base += features
    extras = ["best seller", "premium", "for home", "gift idea", "new 2026"]
    terms = []
    for t in base + extras:
        t = (t or "").strip()
        if t and t.lower() not in [x.lower() for x in terms]:
            terms.append(t)
    return terms[:12]


def _compliance(title: str, bullets: list[str]) -> list[str]:
    notes = []
    if len(title) > 180:
        notes.append("Title is near the 200-character limit; keep core traffic words and cut redundant modifiers.")
    if any(w in title.lower() for w in ["free shipping", "100%", "guaranteed", "sale"]):
        notes.append("Title may contain non-compliant words (free shipping / 100% / guaranteed / sale); Amazon may reject it.")
    if len(bullets) < 5:
        notes.append("Fewer than 5 bullet points; add more to cover benefits and search terms.")
    notes.append("Avoid repeating search terms already in the title; do not use competitor brand names or medical/adult claims.")
    return notes


def _completeness(title: str, bullets: list[str], terms: list[str]) -> float:
    return round(min(100.0, 55 + 9 * len(bullets) + (10 if len(title) <= 200 else 0)
                     + (8 if terms else 0)), 1)


def _parse_json_block(text: str) -> dict:
    """从 LLM 输出中稳健提取 JSON 对象（兼容 ```json 围栏与前后多余文本）。"""
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if m:
        t = m.group(1).strip()
    s, e = t.find("{"), t.rfind("}")
    if s != -1 and e != -1:
        t = t[s:e + 1]
    return json.loads(t)


def _listing_via_agnes(product_name: str, niche: str, features: list[str], tone: str,
                       target_country: str) -> dict:
    """调用 Agnes AI（OpenAI 兼容）真实生成英文 Listing。异常抛出，由上层回退英文模板。"""
    feat_block = "\n".join(f"- {f}" for f in features) or "（未提供）"
    user = (
        f"Write a FULLY ENGLISH Amazon listing for the following product. "
        f"The input may be in Chinese—translate it into native, sales-driven English copy.\n"
        f"Product: {product_name}\nNiche/Scenario: {niche or '(not provided)'}\n"
        f"Key features:\n{feat_block}\nTone: {tone}\nTarget marketplace: {target_country}\n\n"
        "Return STRICT JSON only (no prose), with these keys:\n"
        "- title: string, <=200 chars, lead with core traffic word + top benefit.\n"
        "- bullet_points: array of 5 strings, each one benefit tied to a pain point or proof.\n"
        "- description: string, HTML-free paragraph copy.\n"
        "- search_terms: array of up to 12 backend search terms (English, comma-style phrases).\n"
        "- compliance_notes: array of strings, Amazon compliance/optimization tips (English).\n"
    )
    messages = [
        {"role": "system", "content": "You are a senior Amazon listing copywriter for US/EU marketplaces. Always output native English. Return strict JSON only."},
        {"role": "user", "content": user},
    ]
    text = _agnes.chat(messages, temperature=0.5, max_tokens=1500)
    data = _parse_json_block(text)
    required = {"title", "bullet_points", "description", "search_terms", "compliance_notes"}
    if not required.issubset(data.keys()):
        raise ValueError(f"Agnes listing 缺少字段: {required - data.keys()}")
    bullets = [str(b) for b in data["bullet_points"]][:5]
    terms = [str(t) for t in data["search_terms"]][:12]
    title = str(data["title"])[:200]
    return {
        "product_name": product_name,
        "tone": tone,
        "title": title,
        "bullet_points": bullets,
        "description": str(data["description"]),
        "search_terms": terms,
        "compliance_notes": [str(n) for n in data["compliance_notes"]],
        "completeness_score": _completeness(title, bullets, terms),
    }


def generate_listing(product_name: str, niche_keyword: str = "", key_features: list | None = None,
                     tone: str = "专业可信", target_country: str = "US", language: str = "en") -> dict:
    """Listing 文案生成：优先 Agnes 真实英文；否则英文确定性模板兜底。"""
    raw_features = list(key_features or [])
    # 无 LLM 时，用内置词表把中文产品/卖点/利基译为英文，保证「全英文」输出
    product_name_en = cn_to_en(product_name).title()
    niche_en = cn_to_en(niche_keyword)
    features_en = [cn_to_en(f).title() for f in raw_features]
    if _agnes.enabled():
        try:
            return _listing_via_agnes(product_name, niche_keyword, raw_features, tone, target_country)
        except Exception as e:
            logger.warning("Agnes 英文 Listing 生成失败，回退英文模板: %s", e)
    title = _title(product_name_en, features_en, niche_en, tone)
    bullets = _bullets(product_name_en, features_en, niche_en)
    desc = _description(product_name_en, features_en, niche_en, tone)
    terms = _search_terms(product_name_en, features_en, niche_en)
    notes = _compliance(title, bullets)
    if has_cjk(title + " ".join(bullets) + desc):
        notes.append("Note: some source terms were auto-translated; set AGNES_API_KEY for full Chinese→English copy.")
    return {
        "product_name": product_name_en,
        "tone": tone,
        "title": title,
        "bullet_points": bullets,
        "description": desc,
        "search_terms": terms,
        "compliance_notes": notes,
        "completeness_score": _completeness(title, bullets, terms),
    }


def build_image_plan(product_name: str, niche_keyword: str = "", count: int = 6) -> list[dict]:
    """调用 image_generation 工具，返回主图到附图的生成方案（dict 列表）。"""
    tool = ToolRegistry.get("image_generation")
    res = tool.run({
        "product_name": product_name,
        "niche_keyword": niche_keyword or product_name,
        "count": count,
        "platform": "amazon",
        "style": "ecommerce",
    })
    return res.get("images", [])


LISTING_TOOLS = [
    {
        "name": "generate_listing",
        "description": "英文文案引擎：产品+利基+卖点+语气 → 标题/五点/详情/搜索词/合规提示（全英文，适配欧美站点）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "niche_keyword": {"type": "string"},
                "key_features": {"type": "array", "items": {"type": "string"}},
                "tone": {"type": "string", "enum": ["专业可信", "年轻活力", "高端奢华"]},
                "target_country": {"type": "string", "default": "US"},
                "language": {"type": "string", "default": "en"},
            },
            "required": ["product_name"],
        },
        "handler": generate_listing,
    },
    {
        "name": "build_image_plan",
        "description": "调用 image_generation 工具，生成主图到附图的拍摄/生成方案。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "niche_keyword": {"type": "string"},
                "count": {"type": "integer", "default": 6},
            },
            "required": ["product_name"],
        },
        "handler": build_image_plan,
    },
]
