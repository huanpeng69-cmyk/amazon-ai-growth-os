"""Market Research Agent —— 执行器（取数 → 清洗 → AI 分析 → 报告）。

调用链（严格遵守，Agent 永不直接触达 Bright Data）：
    User → Supervisor → MarketResearchAgent
         → mcp.tools.amazon_research (Tool 层)
         → BrightDataMCPClient (MCP 层)
         → Bright Data

产出约束：
- 取数经 Bright Data MCP；
- 数据先清洗/聚合（脱敏、去噪），再喂给 LLM；
- 最终只输出**经 AI 分析的市场报告**，绝不返回原始抓取数据。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.agents.market_research.prompt import build_messages
from app.agents.market_research.schemas import (
    MarketResearchInput,
    MarketResearchReport,
)
from app.llm.agnes import AgnesError, agnes
from app.mcp.brightdata_client.exceptions import BrightDataError
from app.mcp.tools.amazon_research import amazon_research
from app.mcp.tools.search_web import search_web
from app.tools.base import ToolNotConfigured

_CURRENCY = {
    "US": "USD", "DE": "EUR", "FR": "EUR", "ES": "EUR", "IT": "EUR",
    "JP": "JPY", "UK": "GBP", "CA": "CAD", "AU": "AUD", "MX": "MXN",
}


def _currency_of(country: str) -> str:
    return _CURRENCY.get((country or "US").upper(), "USD")


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> Optional[int]:
    f = _to_float(v)
    return int(f) if f is not None else None


def _extract_json(text: str) -> dict:
    """从 LLM 回复中解析 JSON（兼容 ```json 代码块）。"""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # 去掉可能的首尾非 JSON 字符再试一次
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise AgnesError(f"LLM 返回无法解析为 JSON：{e} | raw={text[:300]}")


class MarketResearchAgent:
    name = "market_research"
    description = "市场调研：国家 + 类目 + 关键词 → 经 Bright Data 取数、清洗、AI 分析，产出市场报告"

    def run(self, inp: MarketResearchInput) -> MarketResearchReport:
        products = self._fetch(inp)
        brief = self._clean(products, inp)
        return self._analyze(brief, inp)

    # —— 1) 取数（Bright Data MCP，经 Tool 层）——
    _FILLER = ["调研一下", "研究一下", "分析一下", "帮我调研", "帮我研究", "帮我分析",
               "调研", "研究", "分析", "一下", "美国", "德国", "日本", "英国",
               "市场", "行业", "的"]

    def _search_term(self, inp: MarketResearchInput) -> str:
        kw = (inp.keyword or "").strip()
        for f in self._FILLER:
            kw = kw.replace(f, " ")
        kw = re.sub(r"\s+", " ", kw).strip()
        if not kw:
            return inp.category
        # 非中文站点上，中文检索词效果差，优先用英文类目
        if any(ord(c) > 127 for c in kw) and inp.country not in ("CN",):
            return inp.category or kw
        return kw

    def _fetch(self, inp: MarketResearchInput) -> List[Dict[str, Any]]:
        kw = self._search_term(inp)
        if not kw:
            raise ToolNotConfigured("市场调研需要类目或关键词")
        try:
            res = amazon_research(keyword=kw, country=inp.country, limit=int(inp.limit))
        except BrightDataError as e:
            raise ToolNotConfigured(f"Bright Data 取数失败，无法生成市场报告：{e.message}")
        products = (res or {}).get("products") or []
        if not products:
            raise ToolNotConfigured(
                f"Bright Data 未返回与「{kw}」相关的商品，无法生成市场报告（请检查关键词/凭证）"
            )
        return products

    def _fetch_web_context(self, inp: MarketResearchInput) -> Optional[List[str]]:
        """可选：用联网搜索补充市场背景（失败不影响主流程）。"""
        kw = (inp.keyword or inp.category or "").strip()
        if not kw:
            return None
        try:
            res = search_web(query=f"{kw} market size {inp.country}", country=inp.country, limit=3)
            return [r.get("snippet") or r.get("title") or "" for r in (res.get("results") or []) if r.get("snippet")]
        except BrightDataError:
            return None

    # —— 2) 数据清洗 / 聚合（脱敏、去噪，仅保留分析所需指标）——
    def _clean(self, products: List[Dict[str, Any]], inp: MarketResearchInput) -> Dict[str, Any]:
        prices = [_to_float(p.get("price")) for p in products]
        prices = [p for p in prices if p is not None]
        ratings = [_to_float(p.get("rating")) for p in products]
        ratings = [r for r in ratings if r is not None]
        reviews = [_to_int(p.get("reviews")) for p in products]
        reviews = [rv for rv in reviews if rv is not None]

        def _score(p: Dict[str, Any]) -> float:
            r = _to_float(p.get("rating")) or 0.0
            rv = _to_int(p.get("reviews")) or 0
            return rv * (r / 5.0 + 1.0)

        top = sorted(products, key=_score, reverse=True)[:5]
        top_clean = [
            {
                "product_name": p.get("title") or p.get("asin") or "未知产品",
                "price": p.get("price"),
                "rating": _to_float(p.get("rating")),
                "reviews": _to_int(p.get("reviews")),
            }
            for p in top
        ]

        brief: Dict[str, Any] = {
            "country": inp.country,
            "category": inp.category,
            "keyword": inp.keyword,
            "sample_size": len(products),
            "price": {
                "min": round(min(prices), 2) if prices else None,
                "max": round(max(prices), 2) if prices else None,
                "avg": round(sum(prices) / len(prices), 2) if prices else None,
                "currency": _currency_of(inp.country),
            },
            "rating": {
                "avg": round(sum(ratings) / len(ratings), 2) if ratings else None,
                "min": min(ratings) if ratings else None,
                "max": max(ratings) if ratings else None,
            },
            "reviews": {
                "avg": int(sum(reviews) / len(reviews)) if reviews else None,
                "max": max(reviews) if reviews else None,
                "min": min(reviews) if reviews else None,
            },
            "top_products": top_clean,
        }
        web_ctx = self._fetch_web_context(inp)
        if web_ctx:
            brief["market_context"] = web_ctx
        return brief

    # —— 3) AI 分析（必须，绝不回退原始数据）——
    def _analyze(self, brief: Dict[str, Any], inp: MarketResearchInput) -> MarketResearchReport:
        messages = build_messages(inp.country, inp.category, inp.keyword, brief)
        # Agnes 偶发返回空响应或被 max_tokens 截断（JSON 不完整）；重试几次以扛过瞬时抖动
        # （仍失败才明确报错，绝不把原始数据当报告返回）。
        report: Optional[MarketResearchReport] = None
        last_err: Optional[Exception] = None
        for _ in range(3):
            try:
                text = agnes.chat(messages, temperature=0.4, max_tokens=3000)
            except AgnesError as e:
                last_err = e
                continue
            if not text or not text.strip():
                last_err = AgnesError("LLM 返回空响应")
                continue
            try:
                data = _extract_json(text)
            except AgnesError as e:
                last_err = e
                continue
            # 由输入决定的字段 LLM 不必回传（prompt 模板未要求），此处补齐
            data.setdefault("country", inp.country)
            data.setdefault("category", inp.category)
            data.setdefault("keyword", inp.keyword)
            try:
                report = MarketResearchReport(**data)
            except Exception as e:  # pydantic validation
                last_err = AgnesError(f"AI 生成的报告结构不完整：{e}")
                continue
            break
        if report is None:
            raise AgnesError(
                f"市场报告必须经过 AI 分析且结构完整，但当前 LLM 不可用（{last_err}）。"
                "请检查 AGNES_API_KEY / 网络后重试。"
            )
        report.country = inp.country
        report.category = inp.category
        report.keyword = inp.keyword
        report.generated_by = "ai"
        report.data_source = "brightdata"
        return report
        # 补齐由输入决定的字段（LLM 不必回传）
        data.setdefault("country", inp.country)
        data.setdefault("category", inp.category)
        data.setdefault("keyword", inp.keyword)
        try:
            report = MarketResearchReport(**data)
        except Exception as e:  # pydantic validation
            raise AgnesError(f"AI 生成的报告结构不完整：{e} | raw={data}")
        report.country = inp.country
        report.category = inp.category
        report.keyword = inp.keyword
        report.generated_by = "ai"
        report.data_source = "brightdata"
        return report
