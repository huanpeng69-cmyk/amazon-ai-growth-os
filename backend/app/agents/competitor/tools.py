"""Competitor Agent —— 工具接口。

scan_competitors：经 Bright Data 实时抓取真实头部竞品（价格/评论/评分），
并对*每个*竞品抓取真实用户评论 → 大模型归纳其软肋（不再用固定递减份额公式，
也不再把一个商品的评论错配给所有竞品）。市场份额无真实数据源，置 None 而非编造。
"""
from __future__ import annotations

import logging
from typing import Dict, List

from app.data.connectors.review_connector.connector import ReviewConnector
from app.agents._util import llm_available, synthesize
from app.llm.agnes import AgnesError

log = logging.getLogger("competitor")

_SYS = (
    "你是亚马逊竞品分析师。只依据提供的真实商品指标与真实用户评论归纳竞品软肋，"
    "绝不编造数据、份额或评论。输出简洁中文。"
)


def _live_competitors(niche_keyword: str, country: str, top_n: int) -> List[dict]:
    try:
        from app.mcp.brightdata_client.exceptions import BrightDataError
        from app.tools.base import ToolNotConfigured
        from app.mcp.tools.amazon_research import amazon_research
        res = amazon_research(keyword=niche_keyword, country=country, limit=max(top_n, 8))
    except (BrightDataError, ToolNotConfigured, ImportError):
        return []
    products = (res or {}).get("products") or []
    out = []
    seen: set[str] = set()
    for p in products:
        name = (p.get("title") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        price_raw = p.get("price")
        price = 0.0
        if price_raw not in (None, ""):
            try:
                price = float(str(price_raw).replace("$", "").replace(",", ""))
            except (TypeError, ValueError):
                price = 0.0
        rev = p.get("reviews")
        rating = p.get("rating")
        out.append({
            "name": name, "asin": p.get("asin"),
            "price_usd": price or 29.9,
            "avg_reviews": rev if isinstance(rev, (int, float)) else 0,
            "rating": rating if isinstance(rating, (int, float)) else 0.0,
        })
    return out[:top_n]


def _gather_reviews(competitors: List[dict], country: str) -> Dict[str, List[str]]:
    rc = ReviewConnector()
    result: Dict[str, List[str]] = {}
    for c in competitors:
        if not c.get("asin"):
            continue
        bodies: List[str] = []
        try:
            raw = rc._fetch_live({"asin": c["asin"], "country": country})
            for r in (raw.payload or {}).get("reviews") or []:
                b = r.get("body") or ""
                if b.strip():
                    bodies.append(b)
        except Exception as e:
            log.warning("Competitor 抓取评论 %s 失败：%s", c["asin"], e)
        if bodies:
            result[c["name"]] = bodies
    return result


def _llm_weaknesses(competitors: List[dict], reviews_map: Dict[str, List[str]], country: str) -> Dict[str, str]:
    if not llm_available() or not reviews_map:
        return {}
    blocks = []
    for c in competitors:
        revs = reviews_map.get(c["name"])
        if revs:
            blocks.append(f"### 竞品：{c['name']}\n" + "\n\n".join(revs)[:2000])
    if not blocks:
        return {}
    prompt = (
        "以下是 Amazon 真实抓取的若干竞品及其用户评论：\n\n" + "\n\n".join(blocks) +
        "\n\n请仅基于评论，为每个竞品归纳其最突出的 1 个软肋（真实存在的短板），"
        "以 JSON 对象返回（键为竞品名，须与「### 竞品：」后的名称一致）：\n"
        "{\"竞品名\": \"软肋中文概述\"}。无评论可归纳的竞品不出现在结果中。"
    )
    try:
        data = synthesize(_SYS, prompt, temperature=0.3, max_tokens=900)
    except AgnesError as e:
        log.warning("Competitor 软肋归纳失败：%s", e)
        return {}
    out: Dict[str, str] = {}
    for c in competitors:
        nm = c["name"]
        if isinstance(data.get(nm), str) and data[nm].strip():
            out[nm] = data[nm].strip()
        else:
            for k, v in data.items():
                if isinstance(v, str) and k.strip() == nm.strip():
                    out[nm] = v.strip()
                    break
    return out


def _llm_summary(competitors: List[dict], weaknesses: Dict[str, str]) -> str:
    if not llm_available() or not competitors:
        return "（未配置大模型，无法生成竞品格局总结）"
    lines = []
    for c in competitors:
        w = weaknesses.get(c["name"], "（暂无真实评论可归纳软肋）")
        lines.append(f"- {c['name']}｜价格 ${c['price_usd']:.2f}｜评论 {c['avg_reviews']}｜评分 {c['rating']}｜软肋：{w}")
    prompt = (
        "以下是真实抓取的头部竞品（指标来自 Amazon 实时数据，软肋来自真实评论归纳）：\n"
        + "\n".join(lines) +
        "\n\n请基于以上真实信息，用 1-2 句中文总结该利基的竞品格局与差异化机会点。"
        "不要编造市场份额数字。"
    )
    try:
        # summary 是自由文本，直接 chat（非 JSON）
        from app.llm.agnes import agnes
        text = agnes.chat([{"role": "system", "content": _SYS},
                           {"role": "user", "content": prompt}], temperature=0.4, max_tokens=400)
        return (text or "").strip() or "（大模型未返回总结）"
    except AgnesError as e:
        log.warning("Competitor 总结失败：%s", e)
        return "（大模型生成总结失败）"


def scan_competitors(niche_keyword: str, country: str = "US", top_n: int = 5) -> dict:
    competitors = _live_competitors(niche_keyword, country, top_n)
    if not competitors:
        return {"profiles": [], "summary": f"未能从 Amazon 检索到「{niche_keyword}」的真实竞品数据。"}

    reviews_map = _gather_reviews(competitors, country)
    weaknesses = _llm_weaknesses(competitors, reviews_map, country)

    profiles = []
    for c in competitors:
        w = weaknesses.get(c["name"], "暂无真实评论可归纳软肋" if c["name"] in reviews_map else "未能获取真实评论数据")
        profiles.append({
            "name": c["name"],
            "price_usd": c["price_usd"],
            "avg_reviews": c["avg_reviews"],
            "rating": c["rating"],
            "est_market_share": None,  # 无真实份额数据源，绝不编造
            "weakness": w,
        })

    summary = _llm_summary(competitors, weaknesses)
    return {"profiles": profiles, "summary": summary}


COMPETITOR_TOOLS = [
    {
        "name": "scan_competitors",
        "description": "扫描指定利基下的头部竞品，返回真实定价/评论量/评分/软肋（数据来自 Bright Data + 真实评论，份额不编造）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "niche_keyword": {"type": "string", "description": "利基/产品关键词"},
                "country": {"type": "string", "description": "站点国家代码", "default": "US"},
                "top_n": {"type": "integer", "description": "竞品数量", "default": 5},
            },
            "required": ["niche_keyword"],
        },
        "handler": scan_competitors,
    },
]
