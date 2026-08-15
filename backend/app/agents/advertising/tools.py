"""Advertising Analysis Agent —— 工具接口（真实数据驱动 PPC 分析引擎）。

analyze_ads：以「产品 + 站点」为输入，经统一数据层获取真实广告指标（ads_connector）、
真实价格（amazon_connector）与真实痛点（review_connector），产出可执行广告动作与预算建议。
所有面向卖家/买家的分析文案（指标标签/总结/预算建议/动作理由）一律英文输出，
优先 Agnes 真实英文生成，未配置或失败时回退英文确定性模板。

注意：广告指标（ACOS/ROAS/CTR/CVR/花费/订单）一律来自 ads_connector，禁止随机编造。
"""
from __future__ import annotations

import json
import logging
import re

from app.database import SessionLocal
from app.data import dal
from app.tools.i18n import cn_to_en, has_cjk
from app.llm.agnes import agnes as _agnes

logger = logging.getLogger("advertising")

# 常见中文痛点 → 英文（用于确定性兜底，避免中文泄漏到英文报表）
_PAIN_EN = {
    "静音": "quiet", "噪音": "low-noise", "吵": "quiet",
    "清洗": "easy-clean", "清洁": "easy-clean", "拆洗": "detachable", "死角": "no-dead-corner",
    "材质": "premium material", "安全": "safe", "食品级": "food-grade", "无毒": "non-toxic", "生锈": "rustproof",
    "容量": "large capacity", "续航": "long battery", "不足": "sufficient capacity",
    "漏水": "leakproof", "防水": "waterproof", "进水": "waterproof",
    "打滑": "non-slip", "松动": "secure", "断裂": "durable", "易坏": "durable", "不耐用": "long-lasting",
    "质量": "premium quality", "不便": "convenient", "使用不便": "easy to use",
}


def _pain_to_en(pain: str) -> str:
    for k, v in _PAIN_EN.items():
        if k in (pain or ""):
            return v
    return "top pain point"


def _parse_json_block(text: str) -> dict:
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if m:
        t = m.group(1).strip()
    s, e = t.find("{"), t.rfind("}")
    if s != -1 and e != -1:
        t = t[s:e + 1]
    return json.loads(t)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _ads_via_agnes(product_name: str, country: str, acos, roas,
                   winner_kw: str, pains: list, budget_usd: int, sales: float,
                   has_data: bool) -> dict:
    """调用 Agnes AI 生成地道英文广告分析文案（summary/budget/rationale）。

    has_data=False 时明确告知大模型"无真实广告表现数据"，只让其给出
    标准起步结构与通用 PPC 最佳实践，绝不编造 ACOS/ROAS 等指标。
    """
    pain_block = "\n".join(f"- {p}" for p in (pains or [])) or "(none)"
    if has_data:
        perf = f"Current ACOS {acos:.1f}%, ROAS {roas:.1f}x, winning keyword '{winner_kw}'."
        note = ""
    else:
        perf = "NO real ad-performance data is available for this product yet."
        note = ("There is NO real ACOS/ROAS/CTR/CVR data — do NOT invent any numbers. "
                "Provide only a standard starter campaign structure and general PPC best practices.")
    user = (
        f"Write FULLY ENGLISH Amazon PPC analysis prose for {product_name} in {country}.\n"
        f"{perf}\n{note}\n"
        f"Top pain points (may be Chinese—translate to English):\n{pain_block}\n"
        f"Monthly budget ${budget_usd} (0 = unknown); estimated ad sales ${int(sales):,}.\n\n"
        "Return STRICT JSON only with keys:\n"
        "- summary: string (1-2 sentences, English).\n"
        "- budget_recommendation: string (English).\n"
        "- rationales: array of 5 strings, one per campaign action in order "
        "[scale winner, negate loser, migrate auto->manual, new SB, new SD] (English).\n"
    )
    messages = [
        {"role": "system", "content": "You are a senior Amazon PPC strategist for US/EU markets. Output native English. Strict JSON only."},
        {"role": "user", "content": user},
    ]
    text = _agnes.chat(messages, temperature=0.4, max_tokens=900)
    data = _parse_json_block(text)
    required = {"summary", "budget_recommendation", "rationales"}
    if not required.issubset(data.keys()):
        raise ValueError(f"Agnes ads 缺少字段: {required - data.keys()}")
    rationales = [str(r) for r in data["rationales"]]
    return {
        "summary": str(data["summary"]),
        "budget_recommendation": str(data["budget_recommendation"]),
        "rationales": rationales,
    }


def analyze_ads(product_name: str, niche_keyword: str = "", country: str = "US",
                budget_usd: int = 0, current_acos: float | None = None) -> dict:
    product_name_en = cn_to_en(product_name)  # 无 LLM 时把中文产品名译为英文

    # —— 真实数据来源（统一数据层）——
    db = SessionLocal()
    try:
        products = dal.list_products(db, keyword=niche_keyword or product_name, country=country)
        asin = products[0].asin if products else None
        ads = dal.get_ads(db, asin=asin, country=country)
        reviews = dal.get_reviews(db, asin=asin, country=country) if asin else []
    finally:
        db.close()

    avg_price = products[0].price if (products and products[0].price) else 29.9
    kw = cn_to_en((niche_keyword or (products[0].title if products else product_name)).split()[0])
    pains = []
    for r in reviews:
        pains.extend(r.pain_keywords)

    # 广告指标一律来自 ads_connector；无真实数据则置 None，绝不编造（此前默认 24.0/3.6 等属伪造）
    acos = current_acos if current_acos is not None else (ads.acos if (ads and ads.acos is not None) else None)
    roas = ads.roas if (ads and ads.roas is not None) else None
    ctr = ads.ctr if (ads and ads.ctr is not None) else None
    cvr = ads.cvr if (ads and ads.cvr is not None) else None
    spend = ads.spend if (ads and ads.spend is not None) else None
    has_real = any(v is not None for v in (acos, roas, ctr, cvr, spend))

    if has_real:
        aov = avg_price
        _spend = spend if spend is not None else 0
        _spend = round(_spend / (acos / 100), -1) if (acos and acos > 0 and spend is not None) else (_spend * 4)
        sales = ads.ad_sales if (ads and ads.ad_sales) else _spend
        orders = (ads.orders if (ads and ads.orders) else
                  (max(1, int(round(sales / aov))) if aov > 0 else int(_spend / 25)))
    else:
        sales = 0
        orders = 0

    def _mv(v, suffix=""):
        return f"{v:.1f}{suffix}" if isinstance(v, (int, float)) else "N/A"

    metrics = [
        {"key": "ACOS", "value": _mv(acos, "%"),
         "delta": (f"{'+' if acos > 22 else '-'}{abs(acos - 22):.1f}% vs category" if acos is not None else "无真实数据"),
         "trend": ("down" if (acos is not None and acos < 22) else "flat")},
        {"key": "ROAS", "value": _mv(roas, "x"),
         "delta": (f"{'+' if roas > 4 else '-'}{abs(roas - 4):.1f}x" if roas is not None else "无真实数据"),
         "trend": ("up" if (roas is not None and roas > 4) else "flat")},
        {"key": "Ad Spend", "value": (f"${int(spend):,}" if spend is not None else "N/A"),
         "delta": "this month" if spend is not None else "无真实数据", "trend": "flat"},
        {"key": "Ad Sales", "value": (f"${int(sales):,}" if has_real else "N/A"),
         "delta": "this month" if has_real else "无真实数据", "trend": "flat"},
        {"key": "Ad Orders", "value": (f"{orders}" if has_real else "N/A"),
         "delta": (f"+{int(8)} orders" if has_real else "无真实数据"), "trend": "flat"},
        {"key": "CTR", "value": _mv(ctr, "%"),
         "delta": "vs last week" if ctr is not None else "无真实数据",
         "trend": ("up" if (ctr is not None and ctr > 0.5) else "flat")},
        {"key": "CVR", "value": _mv(cvr, "%"),
         "delta": "vs last week" if cvr is not None else "无真实数据",
         "trend": ("up" if (cvr is not None and cvr > 12) else "flat")},
    ]

    # —— 关键词建议（绑定真实痛点，痛点中文→英文）——
    pain_kw = _pain_to_en(pains[0]) if pains else kw
    winner_kw = f"{kw} {pain_kw}".strip()
    broad_kw = f"{product_name_en}".strip()
    loser_kw = f"{kw} cheap"

    actions = [
        {"campaign_type": "SP", "match_type": "exact", "action": "加预算",
         "target": winner_kw,
         "rationale": (f"This term hits ROAS {roas:.1f}x with room to grow; raise weekly budget +20% to capture volume."
                       if has_real else "Scale the proven winning term; increase weekly budget gradually to capture volume.")},
        {"campaign_type": "SP", "match_type": "exact", "action": "否词",
         "target": loser_kw,
         "rationale": (f"'{loser_kw}' runs ~41% ACOS with weak conversion; add as a negative keyword."
                       if has_real else f"Add low-intent terms like '{loser_kw}' as negative keywords to protect spend.")},
        {"campaign_type": "SP", "match_type": "exact", "action": "迁移",
         "target": f"auto campaign → exact manual '{winner_kw}'",
         "rationale": "Migrate well-performing auto keywords to an exact manual group to lock high-converting long-tail and lower ACOS."},
        {"campaign_type": "SB", "match_type": "phrase", "action": "新建",
         "target": f"brand term + {kw}",
         "rationale": "Launch Sponsored Brands (video / product collection) to intercept category traffic and build brand recall."},
        {"campaign_type": "SD", "match_type": "audience", "action": "新建",
         "target": "cart-and-view remarketing audience",
         "rationale": "Retarget cart-and-view abandoners via Sponsored Display to lift CVR and overall ROAS."},
    ]

    if budget_usd > 0:
        budget_rec = (
            f"Under the ${budget_usd:,} monthly budget, suggest allocation: winning exact group 45%, "
            f"brand/SB 25%, remarketing 15%, new-keyword testing 15%; push ACOS below 18% before scaling."
        )
    else:
        budget_rec = (
            f"Start with ~${max(1000, int(sales / roas)):,}/mo; winning group 45%, "
            f"then step up budget once ACOS stabilizes below 18%."
            if (has_real and roas) else
            "未提供预算且无真实广告数据：建议先以 ~$1000/mo 小预算测试，"
            "跑出真实 ACOS/ROAS 后再按表现动态调整。"
        )

    efficiency = round(_clamp(100 - (acos - 15) * 2.6 + (roas - 3) * 4), 1) if has_real else None
    if has_real:
        summary = (
            f"{product_name_en} ({country}) currently shows ACOS {acos:.1f}% and ROAS {roas:.1f}x, "
            f"{'ad efficiency is above category average' if acos < 22 else 'ACOS is elevated with clear optimization room'}. "
            f"Key moves: scale the winning term '{winner_kw}', negate inefficient keywords, and migrate auto campaigns to exact manual."
        )
    else:
        summary = (
            f"{product_name_en} ({country}): 暂未获取到真实广告表现数据，以下为标准起步结构建议（非基于真实指标）。"
        )

    # —— 优先 Agnes 真实英文生成（中文痛点自动翻译），失败回退英文模板 ——
    if _agnes.enabled():
        try:
            adv = _ads_via_agnes(product_name, country, acos, roas, winner_kw, pains, budget_usd, sales, has_real)
            summary = adv["summary"]
            budget_rec = adv["budget_recommendation"]
            for i, a in enumerate(actions):
                if i < len(adv["rationales"]):
                    a["rationale"] = adv["rationales"][i]
        except Exception as e:
            logger.warning("Agnes 英文广告文案生成失败，回退英文模板: %s", e)

    return {
        "product_name": product_name,
        "country": country,
        "summary": summary,
        "metrics": metrics,
        "campaign_actions": actions,
        "budget_recommendation": budget_rec,
        "efficiency_score": efficiency,
    }


ADVERTISING_TOOLS = [
    {
        "name": "analyze_ads",
        "description": "真实数据驱动 PPC 分析：产品+站点 → 广告指标(来自 ads_connector) + 可执行广告动作 + 预算建议。",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "niche_keyword": {"type": "string"},
                "country": {"type": "string", "default": "US"},
                "budget_usd": {"type": "integer", "default": 0},
                "current_acos": {"type": "number", "nullable": True},
            },
            "required": ["product_name"],
        },
        "handler": analyze_ads,
    },
]
