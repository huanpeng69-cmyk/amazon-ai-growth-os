"""Tool：amazon_research —— Amazon 商品/市场研究（经 Bright Data MCP）。

调用链路：Agent → mcp.tools.amazon_research → BrightDataMCPClient → Bright Data。

实现说明
--------
Bright Data MCP **没有** amazon_search / amazon_product 这类专用工具（真实可用工具为
``ask_brightdata_assistant`` / ``search_engine`` / ``scrape_as_markdown`` /
``search_engine_batch`` / ``scrape_batch``）。因此这里走最稳的路径：

1. 用关键词 + 国家拼出 Amazon 搜索页 URL（如 ``https://www.amazon.com/s?k=...``）；
2. 调用 ``scrape_as_markdown`` 抓取该 SERP 的 Markdown；
3. 解析 Markdown，提取每个商品的 ``asin / title / price / rating / reviews / url``。

同时保留**结构化 JSON 路径**：当上游返回的是已结构化的商品 JSON（如离线 Mock /
测试注入）时，直接做字段归一化，保证单测与历史契约不变。

统一返回 JSON：
    {
      "keyword": str,
      "country": str,
      "count": int,
      "products": [
        {"asin","title","price","rating","reviews","category","url"}, ...
      ]
    }
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from app.mcp.brightdata_client.exceptions import BrightDataError
from app.mcp.tools._common import _int, _money, _num, coerce_list, make_client


# ───────────────────────── 国家 → Amazon 域名 ─────────────────────────
_DOMAIN = {
    "US": "amazon.com",
    "UK": "amazon.co.uk", "GB": "amazon.co.uk",
    "DE": "amazon.de", "FR": "amazon.fr", "ES": "amazon.es", "IT": "amazon.it",
    "JP": "amazon.co.jp",
    "CA": "amazon.ca", "AU": "amazon.com.au", "MX": "amazon.com.mx",
    "IN": "amazon.in", "BR": "amazon.com.br", "NL": "amazon.nl",
    "SE": "amazon.se", "PL": "amazon.pl", "BE": "amazon.com.be",
    "SG": "amazon.sg", "AE": "amazon.ae", "SA": "amazon.sa",
    "TR": "amazon.com.tr", "EG": "amazon.eg",
}


def _domain_of(country: str) -> str:
    return _DOMAIN.get((country or "US").upper(), "amazon.com")


def _serp_url(keyword: str, country: str) -> str:
    kw = quote((keyword or "").strip())
    return f"https://{_domain_of(country)}/s?k={kw}"


# ───────────────────────── 结构化 JSON 归一化 ─────────────────────────
def _normalize_product(it: Dict[str, Any]) -> Dict[str, Any]:
    asin = it.get("asin") or it.get("ASIN") or it.get("product_id")
    url = it.get("url") or (f"https://www.amazon.com/dp/{asin}" if asin else None)
    return {
        "asin": asin,
        "title": (it.get("title") or it.get("name") or "").strip(),
        "price": _money(it.get("price") or it.get("current_price") or it.get("buybox_price")),
        "rating": _num(it.get("rating") or it.get("stars") or it.get("rating_value")),
        "reviews": _int(it.get("reviews") or it.get("review_count") or it.get("reviews_count") or it.get("ratings_total")),
        "category": it.get("category") or it.get("category_name") or it.get("node_name"),
        "url": url,
    }


# ───────────────────────── Markdown SERP 解析 ─────────────────────────
# 去掉 Bright Data 注入的 SECURITY NOTICE 包裹层
_WRAP_RE = re.compile(
    r"=====UNTRUSTED_.*?_BEGIN=====(.*?)=====UNTRUSTED_.*?_END=====", re.DOTALL
)
# 还原 Markdown 转义：\[ \] \( \) \* _ # > .  →  原字符
_UNESCAPE_RE = re.compile(r"\\([\[\]()*_#>.])")
# 商品标题链接：[标题](/路径/.../dp/ASIN/...) 或 [(...)] 评论链接。
# 注意：自然搜索结果用「相对路径」(/xxx/dp/ASIN)；广告/联盟卡用 aax-*.amazon.com 重定向，
# 其 URL 巨长（2k+ 字符），会把真正的 价格/评分 推到更后面 —— 解析时优先采用相对路径链接。
_TITLE_LINK_RE = re.compile(
    r"\[([^\]]+)\]\(\s*(?:https?://[a-z.\-]*amazon\.com)?"
    r"(/[^\s)]*?/dp/([A-Z0-9]{10})[^\s)]*?)\)",
    re.IGNORECASE,
)
_RATING_RE = re.compile(r"(\d\.\d)\s+out of 5 stars")
# 评论数链接：[(2.5K)](...#customerReviews)
_REVIEWS_RE = re.compile(r"\[\(([\d.,]+[KMB]?)\)\]\([^\s)]*customerReviews", re.IGNORECASE)
_REVIEWS_FALLBACK_RE = re.compile(r"\(([\d.,]+[KMB]?)\)\s*(?:ratings?|reviews?)", re.IGNORECASE)
_PRICE_RE = re.compile(r"\$\s*([\d,]+\.?\d*)")
# 明显不是商品的垃圾标题（页面 dev 残留 / 按钮文案等）
_JUNK_TITLE_RE = re.compile(
    r"debug info|add to cart|see more|sponsored|previous page|next page|"
    r"^\s*results?\s*$|^\s*filters?\s*$|sign in|hello,",
    re.IGNORECASE,
)
# 图书 / 影视 / 电子书等非实体电商商品（搜索宽泛类目时 Amazon SERP 会混入）。
# 这些结果不应进入「电商选品」分析。
_BOOK_RE = re.compile(
    r"(^|\b)("
    r"kindle|paperback|hardcover|audiobook|mass\s*market|spiral[-\s]?bound|"
    r"boxed\s*set|box\s*set|"
    r"kindle\s*edition|first\s*edition|collector'?s\s*edition|annotated\s*edition|"
    r"revised\s*edition|illustrated\s*edition|deluxe\s*edition|"
    r"would\s*you\s*rather|wacky\s*facts|facts\s*about|for\s*dummies|"
    r"coloring\s*book|activity\s*book|word\s*search|crossword|puzzle\s*book|"
    r"guided\s*journal|study\s*guide|workbook|cheat\s*sheet|"
    r"trivia\s*book|quiz\s*book|"
    r"book\s+\d+|,\s*book\b|:\s*book\b|"  # 丛书续作（如 "..., Book 5"）
    r"beauty\s*(and|&)\s*the\s*(beast|billionaire)|beauty\s*shop"
    r")\b",
    re.IGNORECASE,
)
# 图书 / 影视常见的「主标题: 副标题（成句描述）」句式，实体商品极少这样写。
_BOOK_COLON_RE = re.compile(
    r":\s*(a\s+collection|an\s+empowering|an\s+inspiring|inspirational|"
    r"fascinating\s+stories|amazing\s+trivia|fun\s+facts|the\s+complete\s+guide|"
    r"a\s+playbook|stories\s+for|quizzes?\s+and|the\s+ultimate\s+guide|"
    r"everything\s+you\s+need\s+to\s+know)",
    re.IGNORECASE,
)
# Amazon 顶部导航 / 部门入口（不是商品）：Prime Video、Blu-ray、Books 等
_NAV_RE = re.compile(
    r"^(prime\s*video|blu-?ray|vhs|dvd|audible|amazon\s*music|amazon\s*fresh|"
    r"whole\s*foods|today'?s\s*deals|customer\s*service|gift\s*cards|kindle\s*store|"
    r"amazon\s+ads|best\s+sellers?)\b",
    re.IGNORECASE,
)
# Prime Video 租赁 / 购买 CTA 碎片（如 "For $3.99 to rent" / "For $19.99$19.99 to buy"）
_VIDEO_CTA_RE = re.compile(
    r"^for\s+\$.*?(to\s+(rent|buy)|rental)", re.IGNORECASE
)


# 价格 / 列表价 等纯数字碎片（如 "$6.20$6.20 List: $7.99 List: $7.99$7.99"）。
# 这些来自 SERP 里把「价格」本身渲染成可点击链接的锚文本，不是真实商品。
def _looks_like_price_fragment(title: str) -> bool:
    s = re.sub(r"\$\s*[\d.,]+", " ", title)              # 去掉 $6.20 等价格
    s = re.sub(r"\b(list|price|listprice)\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"[^A-Za-z]", "", s)                       # 只留字母
    return len(s) < 3                                      # 没有 >=3 个实质字母 → 视为碎片


def _is_organic(url_path: str) -> bool:
    """相对路径（以 / 开头）为自然结果；aax-* 重定向为广告/联盟卡。"""
    return url_path.startswith("/")


def _parse_count(s: str) -> Optional[int]:
    """2.5K → 2500, 1.2M → 1200000, 3,400 → 3400。"""
    if not s:
        return None
    s = s.strip().replace(",", "").upper()
    mult = 1
    if s.endswith("K"):
        mult, s = 1_000, s[:-1]
    elif s.endswith("M"):
        mult, s = 1_000_000, s[:-1]
    elif s.endswith("B"):
        mult, s = 1_000_000_000, s[:-1]
    try:
        return int(float(s) * mult)
    except (TypeError, ValueError):
        return None


def _parse_serp_markdown(text: str, limit: int) -> List[Dict[str, Any]]:
    if not text:
        return []
    wrap = _WRAP_RE.search(text)
    body = wrap.group(1) if wrap else text
    u = _UNESCAPE_RE.sub(r"\1", body)

    # 先收集所有标题链接，再按 ASIN 去重：
    # - 跳过明显垃圾标题（dev 残留 / 按钮文案）
    # - 同一 ASIN 优先保留「自然结果（相对路径）」链接
    candidates: List[Dict[str, Any]] = []
    for lm in _TITLE_LINK_RE.finditer(u):
        asin = lm.group(3)
        title = re.sub(r"\s+", " ", lm.group(1)).strip()
        if not title or len(title) < 4 or _JUNK_TITLE_RE.search(title):
            continue
        if _BOOK_RE.search(title):  # 剔除图书 / 影视 / 电子书等非实体商品
            continue
        if _BOOK_COLON_RE.search(title):  # 剔除「主标题: 成句副标题」式图书
            continue
        if _NAV_RE.match(title):  # 剔除 Amazon 顶部导航 / 部门入口（非商品）
            continue
        if _VIDEO_CTA_RE.match(title):  # 剔除 Prime Video 租赁/购买 CTA 碎片
            continue
        # 跳过价格 / 列表价 等纯数字碎片（如 "$6.20$6.20 List: $7.99..."）
        if _looks_like_price_fragment(title):
            continue
        candidates.append({
            "asin": asin,
            "title": title,
            "path": lm.group(2),
            "organic": _is_organic(lm.group(2)),
            "start": lm.start(),
            "end": lm.end(),
        })

    best: Dict[str, Dict[str, Any]] = {}
    for c in candidates:
        cur = best.get(c["asin"])
        if cur is None or (not cur["organic"] and c["organic"]):
            best[c["asin"]] = c
    chosen = list(best.values())

    products: List[Dict[str, Any]] = []
    for c in chosen:
        # 卡片窗口：标题链接之后（价格/评分/评论均在其后）；广告卡 URL 巨长，放宽到 5000
        window = u[c["end"]: c["end"] + 5000]

        m_price = _PRICE_RE.search(window)
        price = _money(m_price.group(1)) if m_price else None
        m_rating = _RATING_RE.search(window)
        rating = _num(m_rating.group(1)) if m_rating else None
        m_rev = _REVIEWS_RE.search(window) or _REVIEWS_FALLBACK_RE.search(window)
        reviews = _parse_count(m_rev.group(1)) if m_rev else None

        products.append({
            "asin": c["asin"],
            "title": c["title"],
            "price": price,
            "rating": rating,
            "reviews": reviews,
            "category": None,
            "url": f"https://www.amazon.com/dp/{c['asin']}",
        })

    return products[:limit]


# ───────────────────────── 对外入口 ─────────────────────────
def amazon_research(
    keyword: str,
    country: str = "US",
    category: Optional[str] = None,
    limit: int = 10,
    api_key: Optional[str] = None,
    endpoint: Optional[str] = None,
    transport: Optional[Any] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """检索 Amazon 商品，返回统一归一化 JSON。

    参数
    ----
    keyword: 搜索关键词（如 "cat water fountain"）
    country: 站点国家码（US/DE/JP/UK...）
    category: 可选类目过滤（仅作上下文携带，不影响实时抓取 URL）
    limit: 返回商品数
    """
    if not keyword or not keyword.strip():
        raise BrightDataError("amazon_research 需要非空的 keyword")

    url = _serp_url(keyword, country)

    # 离线 / Mock / 测试：注入 transport 时直接走它就是，不碰网络
    client = make_client(api_key=api_key, endpoint=endpoint, transport=transport, timeout=timeout)

    try:
        raw = client.call_tool("scrape_as_markdown", {"url": url})
    except BrightDataError:
        raise
    except Exception as e:  # 网络/协议层异常，统一包装
        raise BrightDataError(f"Bright Data scrape_as_markdown 调用失败：{e}") from e

    # 路径 A：上游已返回结构化商品 JSON（Mock / 测试）
    if isinstance(raw, dict) and any(k in raw for k in ("products", "results", "items", "data")):
        items: List[Dict[str, Any]] = coerce_list(raw)[:limit]
        products = [_normalize_product(it) for it in items if isinstance(it, dict)]
        return {"keyword": keyword, "country": country, "count": len(products), "products": products}

    # 路径 B：Markdown（实时 scrape_as_markdown）
    text = raw if isinstance(raw, str) else (
        (raw.get("content") or raw.get("markdown") or raw.get("text"))
        if isinstance(raw, dict) else ""
    )
    text = text or ""
    products = _parse_serp_markdown(text, limit)
    if not products:
        raise BrightDataError(
            f"Bright Data 未能从「{keyword}」的 Amazon SERP 解析出商品（可能被风控或返回空页）"
        )
    return {"keyword": keyword, "country": country, "count": len(products), "products": products}
