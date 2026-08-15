"""Review Connector —— 商品评论 / VOC 原料。

真实数据源：Amazon 商品详情页（经 Bright Data MCP 的 scrape_as_markdown）。
- Amazon 评论页（/product-reviews/{asin}）为 JS 懒加载，服务端 markdown 抓回空壳；
  故改抓 **商品详情页 /dp/{asin}**，其初始 HTML 内嵌了「顾客评论」段落（真实评论正文）。
- fixture：connectors/review_connector/fixtures/sample.json（真实样本评论，非随机生成）。

取数策略（与 BaseConnector 一致，live 优先、失败降级 fixture）：
- 全局 BRIGHTDATA_API_KEY 就绪即走 live（与 amazon_research 同源），
  任何失败（无凭证 / 风控 / 解析为空）抛出 ConnectorNotConfigured → 自动降级 fixture / 空，
  DAL 的 except ConnectorError 会将其收敛为 []，绝不触发 500。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from app.data.base import BaseConnector, RawData
from app.data.exceptions import ConnectorNotConfigured, DataNotFound


# ───────────────────────── Markdown 解析（评论页） ─────────────────────────
_WRAP_RE = re.compile(
    r"=====UNTRUSTED_.*?_BEGIN=====(.*?)=====UNTRUSTED_.*?_END=====", re.DOTALL
)
_RATE_RE = re.compile(r"(\d(?:\.\d)?)\s*out of 5 stars", re.IGNORECASE)
_DATE_RE = re.compile(r"Reviewed in .*? on ([A-Z][a-z]+ \d{1,2}, \d{4})")
_VP_RE = re.compile(r"Verified Purchase", re.IGNORECASE)
_TITLE_LINK_RE = re.compile(r"\]\(/portal/customer-reviews/")
_BOILER = re.compile(
    r"^(brief content visible|full content visible|double tap to read|"
    r"report|permalink|helpful|comment|cancel|translate|see more|hide)\b",
    re.IGNORECASE,
)
_LINK_LINE_RE = re.compile(r"\]\(/(gp|portal|customer-reviews|stores)")


def _unwrap(text: str) -> str:
    if not text:
        return ""
    m = _WRAP_RE.search(text)
    return m.group(1) if m else text


# 痛点词库：正则 → 规范化痛点关键词（与 fixture 英文风格一致）。
# 仅做「真实评论正文中的投诉短语」提取，不编造。
_PAIN_LEXICON = [
    (r"leak\w*", "漏水/leaking"),
    (r"drip\w*", "滴水/dripping"),
    (r"nois\w*|loud|racket|rattl\w*", "噪音/noisy"),
    (r"hard to clean|difficult to clean|tough to clean|not easy to clean|hard to wash|difficult to wash", "难清洗/hard to clean"),
    (r"cheap\w*|flimsy|fragile|break\w*|broke|broken|fell apart|crack\w*", "做工差/cheap"),
    (r"stop(ped)? working|quit working|died|no longer work|stopped", "停止工作/stopped working"),
    (r"bad (smell|odor|odour)|smell(s)? (bad|funny|weird|fishy)|stink\w*", "异味/bad smell"),
    (r"poor (quality|build)|low quality|cheaply made", "质量差/poor quality"),
    (r"small(er)?|too small|tiny", "太小/too small"),
    (r"big|too big|bulky|huge", "太大/too big"),
    (r"short battery|battery (life|dies|dead|drain)|runs out", "续航短/short battery"),
    (r"overheat\w*", "过热/overheating"),
    (r"confus\w*|complicated|hard to (use|set up|setup)|difficult to (use|set up)|not intuitive|confusing", "难用/hard to use"),
    (r"mislead\w*|not as described|false|deceptive|wrong (item|product|size)", "货不对板/misleading"),
    (r"customer (service|support)|warranty|refund\w*|return\w*", "售后/customer service"),
    (r"disappoint\w*|regret|waste\w*|useless", "失望/disappointing"),
    (r"uncomfortable|itchy|scratchy", "不适/uncomfortable"),
    (r"defect\w*", "缺陷/defective"),
    (r"rust\w*", "生锈/rusting"),
    (r"expensive|overpriced|too pricey|over priced", "偏贵/too expensive"),
    (r"doesn'?t work|does not work|not working|won'?t work|never worked", "不工作/doesn't work"),
    (r"mold\w*|mildew", "发霉/mold"),
    (r"water (taste|tastes|tasted) (bad|funny|odd)|bad taste|taste(s)? (bad|funny|odd)", "水有异味/bad taste"),
    (r"slow\w*", "慢/slow"),
    (r"instruction\w*|manual|hard to (figure|assemble)", "说明差/poor instructions"),
    (r"filter\w* (clog|dirty|replace)|hard to (replace|change) filter", "滤芯/filter issue"),
    (r"pump (stop|died|fail|noise)|pump\w* (broken|loud)", "水泵问题/pump issue"),
]
_PAIN_COMPILED = [(re.compile(p, re.IGNORECASE), c) for p, c in _PAIN_LEXICON]


def _extract_pain_keywords(body: str) -> List[str]:
    if not body:
        return []
    out: List[str] = []
    for rx, canon in _PAIN_COMPILED:
        for mm in rx.finditer(body):
            # 否定语境（not / no / never / n't / without）下不计为痛点，降低误报
            pre = body[max(0, mm.start() - 20):mm.start()].lower()
            if any(w in pre for w in ("not ", "no ", "never ", "n't ", "without ", "barely ")):
                continue
            if canon not in out:
                out.append(canon)
            break
    return out


def _clean_body(seg: str) -> str:
    # 正文起点：Verified Purchase 或 日期行 之后
    cands = []
    m_vp = _VP_RE.search(seg)
    m_dt = _DATE_RE.search(seg)
    if m_vp:
        cands.append(m_vp.end())
    if m_dt:
        cands.append(m_dt.end())
    if cands:
        seg = seg[min(cands):]
    lines = seg.splitlines()
    kept: List[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if _RATE_RE.search(s):
            continue
        if _DATE_RE.search(s):
            continue
        if _VP_RE.search(s):
            continue
        if _TITLE_LINK_RE.search(s):
            continue
        if _BOILER.match(s):
            continue
        if _LINK_LINE_RE.search(s):
            continue
        kept.append(s)
    body = " ".join(kept)
    body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body)  # 还原行内链接为纯文本
    body = re.sub(r"\s+", " ", body).strip()
    return body[:2000]


def _parse_reviews_markdown(text: str, max_reviews: int = 40) -> List[Dict[str, Any]]:
    """从商品详情页 markdown 抽取真实评论。

    仅保留含「Reviewed in ... on」结构的段落（剔除聚合评分 / 交叉销售等假评论）。
    """
    text = _unwrap(text or "")
    if not text:
        return []
    matches = list(_RATE_RE.finditer(text))
    if not matches:
        return []
    reviews: List[Dict[str, Any]] = []
    seen: set = set()
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg = text[start:end]
        if not _DATE_RE.search(seg):      # 无「Reviewed in」→ 非真实评论，跳过
            continue
        rating = float(m.group(1))
        date_m = _DATE_RE.search(seg)
        reviewed_at = date_m.group(1) if date_m else None
        is_vp = bool(_VP_RE.search(seg))
        body = _clean_body(seg)
        if not body:
            continue
        key = body[:120].lower()
        if key in seen:                   # 去重：同一评论在页面多区块重复出现
            continue
        seen.add(key)
        reviews.append({
            "rating": rating,
            "body": body,
            "is_vp": is_vp,
            "reviewed_at": reviewed_at,
            "pain_keywords": _extract_pain_keywords(body),
        })
        if len(reviews) >= max_reviews:
            break
    return reviews


class ReviewConnector(BaseConnector):
    name = "review"
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "sample.json"

    # 重写 fetch：review live 真实数据源 = Bright Data（抓商品详情页评论），
    # 与 amazon_research 同源；live 失败自动降级 fixture / 空，绝不 500。
    def fetch(self, query: Dict[str, Any]) -> RawData:
        try:
            return self._fetch_live(query)
        except ConnectorNotConfigured:
            return self._fetch_fixture(query)

    def _fetch_live(self, query: Dict[str, Any]) -> RawData:
        asin = query.get("asin")
        country = (query.get("country") or "US")
        if not asin:
            raise ConnectorNotConfigured("review live 需要 asin")
        # 懒加载，避免模块加载期循环依赖
        try:
            from app.mcp.brightdata_client.exceptions import BrightDataError
            from app.mcp.tools._common import make_client
            from app.mcp.tools.amazon_research import _domain_of
        except Exception:
            raise ConnectorNotConfigured("review live 依赖的 Bright Data 客户端不可用")

        try:
            url = f"https://{_domain_of(country)}/dp/{asin}"
            client = make_client(timeout=45)
            raw = client.call_tool("scrape_as_markdown", {"url": url})
        except BrightDataError as e:
            raise ConnectorNotConfigured(f"review live 抓取失败：{e}")
        except Exception as e:
            raise ConnectorNotConfigured(f"review live 调用异常：{e}")

        text = raw if isinstance(raw, str) else (
            (raw.get("content") or raw.get("markdown") or raw.get("text")) if isinstance(raw, dict) else ""
        )
        reviews = _parse_reviews_markdown(text)
        if not reviews:
            raise ConnectorNotConfigured("review live 未能从商品页解析出评论（可能被风控或返回空页）")
        return RawData(
            connector=self.name,
            query=query,
            source="live",
            payload={"country": country, "asin": asin, "reviews": reviews},
        )

    def _fetch_fixture(self, query: Dict[str, Any]) -> RawData:
        data = self._load_fixture()
        asin = query.get("asin")
        country = (query.get("country") or "US")
        reviews = data.get("by_asin", {}).get(asin)
        if not reviews:
            raise DataNotFound(f"review_connector 未找到评论：asin={asin}")
        return RawData(
            connector=self.name,
            query=query,
            source="fixture",
            payload={"country": country, "asin": asin, "reviews": reviews},
        )
