"""VOC Agent —— 执行器（网上搜评论 → 大模型归纳痛点 → 大模型给建议）。

端到端真实链路：
  1. 用 Bright Data 在 Amazon 搜索产品名 → 拿到真实商品 ASIN；
  2. 用 Bright Data 抓取这些商品详情页的真实用户评论（原文）；
  3. 把真实评论原文交给 Agnes 大模型，归纳痛点并给出改进建议；
  4. 大模型不可用时，降级为正则启发式（仅兜底，不编造建议）。

设计原则：
- 建议由大模型基于真实评论生成，绝不依赖硬编码的模板映射（此前"文不对题"即源于此）；
- 抓不到真实评论时明确告知，绝不编造数据。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.agents.voc.schemas import PainPointOut, VOCInput, VOCOutput
from app.data.connectors.review_connector.connector import (
    ReviewConnector,
    _extract_pain_keywords,
)
from app.llm.agnes import AgnesError, agnes
from app.mcp.brightdata_client.exceptions import BrightDataError
from app.mcp.tools.amazon_research import amazon_research

log = logging.getLogger(__name__)

_MAX_REVIEWS_CHARS = 9000
_TOP_ASINS = 3


def _extract_json(text: str) -> dict:
    """从 LLM 回复中稳健解析 JSON（兼容 ```json 代码块与前后多余文本）。"""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except json.JSONDecodeError:
                pass
        raise AgnesError(f"LLM 返回无法解析为 JSON：{text[:300]}")


class VOCAgent:
    name = "voc"
    description = "用户声音分析：产品名 → 网上搜真实评论 → 大模型归纳痛点 + 改进建议"

    def run(self, inp: VOCInput) -> VOCOutput:
        gathered = self._gather_reviews(inp.product_name, inp.country)
        product_label = gathered["product_name"] or inp.product_name
        review_text = gathered["review_text"].strip()

        # 没抓到任何真实评论 → 明确告知，绝不编造
        if not review_text:
            return VOCOutput(
                product_name=product_label,
                country=inp.country,
                pain_points=[],
                strengths=[],
                summary=(
                    f"未能从 Amazon 检索到「{inp.product_name}」的真实用户评论"
                    f"（可能是关键词过窄、被风控或该站点无此类目）。"
                    f"建议换成更通用的产品名，或确认 Bright Data 凭证有效。"
                ),
            )

        # 优先：大模型基于真实评论归纳痛点 + 给建议
        if agnes.enabled():
            try:
                llm = self._analyze_with_llm(product_label, review_text, gathered["count"])
                return self._to_output(product_label, inp.country, llm)
            except AgnesError as e:
                log.warning("VOC 大模型分析失败，降级启发式：%s", e)
                heur = self._heuristic(product_label, review_text)
                return self._to_output(product_label, inp.country, heur)

        # 大模型未配置 → 启发式兜底
        log.info("VOC 未配置 AGNES_API_KEY，走启发式兜底")
        heur = self._heuristic(product_label, review_text)
        return self._to_output(product_label, inp.country, heur)

    # ── 1) 搜索 + 抓真实评论 ──
    def _gather_reviews(self, product_name: str, country: str) -> Dict[str, Any]:
        asins: List[str] = []
        found_title = product_name
        try:
            res = amazon_research(keyword=product_name, country=country, limit=8)
            products = (res or {}).get("products") or []
            for p in products:
                a = p.get("asin")
                if a:
                    asins.append(a)
                    if found_title == product_name and p.get("title"):
                        found_title = p["title"]
                if len(asins) >= _TOP_ASINS:
                    break
        except BrightDataError:
            log.warning("VOC 搜索 %s 失败（Bright Data 不可用）", product_name)

        bodies: List[str] = []
        if asins:
            rc = ReviewConnector()
            for asin in asins:
                try:
                    raw = rc._fetch_live({"asin": asin, "country": country})
                except Exception as e:  # 单个 ASIN 失败不影响其他
                    log.warning("VOC 抓取评论 %s 失败：%s", asin, e)
                    continue
                for r in (raw.payload or {}).get("reviews") or []:
                    b = r.get("body") or ""
                    if b.strip():
                        bodies.append(b)
        text = "\n\n".join(bodies)
        if len(text) > _MAX_REVIEWS_CHARS:
            text = text[:_MAX_REVIEWS_CHARS]
        return {"product_name": found_title, "review_text": text, "count": len(bodies), "asins": asins}

    # ── 2) 大模型分析 ──
    def _analyze_with_llm(self, product: str, review_text: str, count: int) -> Dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是资深的亚马逊选品与用户体验（VOC）分析师。"
                    "你只依据用户提供的真实评论原文做分析，绝不编造任何评论、数据或产品事实。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"产品（检索词）：{product}\n"
                    f"以下是我们在 Amazon 上真实抓取的该品类用户评论原文"
                    f"（约 {max(count, 1)} 条，已截断）：\n\n"
                    f"{review_text}\n\n"
                    "请基于以上真实评论完成分析，并以 JSON 返回（不要输出 JSON 以外的解释）：\n"
                    "{\n"
                    '  "pain_points": [\n'
                    '    {"pain": "痛点中文概述（如：笔尖易断、墨水易晕染）",\n'
                    '     "severity": 0-100 的整数（综合出现频率与负面影响程度）,\n'
                    '     "evidence": 估计提及该痛点的评论条数（整数）,\n'
                    '     "typical_review": "最能代表该痛点的英文评论原句（必须从上面文本摘取，不要改写）",\n'
                    '     "suggested_fix": "针对该痛点、结合评论的具体可落地改进建议（中文，1-2句）"}\n'
                    "  ],\n"
                    '  "strengths": ["2-3 条该产品被用户称赞的优势（中文）"],\n'
                    '  "summary": "一句话总结：最突出痛点与最大机会点（中文）"\n'
                    "}\n"
                    "要求：pain_points 最多 6 条，按 severity 从高到低排序；"
                    "只列真实出现在评论中的痛点；typical_review 必须来自提供的文本。"
                ),
            },
        ]
        last_err: Optional[Exception] = None
        data: Optional[dict] = None
        for _ in range(3):  # 扛过 LLM 偶发空响应 / JSON 截断
            try:
                text = agnes.chat(messages, temperature=0.3, max_tokens=2000)
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
            break
        if data is None:
            raise AgnesError(f"VOC 大模型分析失败：{last_err}")
        return data

    # ── 3) 启发式兜底（仅大模型不可用时）──
    def _heuristic(self, product: str, review_text: str) -> Dict[str, Any]:
        counter: Dict[str, int] = {}
        for para in review_text.split("\n\n"):
            for pk in _extract_pain_keywords(para):
                counter[pk] = counter.get(pk, 0) + 1
        pains = []
        for k, v in sorted(counter.items(), key=lambda x: -x[1])[:6]:
            pains.append({
                "pain": k,
                "severity": min(100, 45 + v * 5),
                "evidence": v,
                "typical_review": "",
                "suggested_fix": f"针对「{k}」对{product}做针对性优化",
            })
        return {
            "pain_points": pains,
            "strengths": ["（启发式降级）配置 AGNES_API_KEY 后可获得大模型洞察"],
            "summary": (
                f"「{product}」基于真实评论正则识别 {len(pains)} 个痛点；"
                f"配置大模型后可获得归纳与建议。"
            ),
        }

    # ── 4) 映射到输出 schema ──
    def _to_output(self, product: str, country: str, data: Dict[str, Any]) -> VOCOutput:
        raw_pts = (data.get("pain_points") or [])
        pain_points: List[PainPointOut] = []
        for p in raw_pts:
            if not isinstance(p, dict):
                continue
            pain = (p.get("pain") or "").strip()
            if not pain:
                continue
            try:
                sev = float(p.get("severity") or 50)
            except (TypeError, ValueError):
                sev = 50.0
            sev = max(0.0, min(100.0, sev))
            try:
                ev = int(p.get("evidence") or 1)
            except (TypeError, ValueError):
                ev = 1
            ev = max(1, ev)
            fix = (p.get("suggested_fix") or f"针对「{pain}」做针对性优化").strip()
            pain_points.append(PainPointOut(
                pain=pain, severity=round(sev, 1), evidence=ev, suggested_fix=fix))
        pains_out = sorted(pain_points, key=lambda x: x.severity, reverse=True)
        strengths = [str(s) for s in (data.get("strengths") or []) if str(s).strip()][:3]
        summary = (data.get("summary") or "").strip()
        if not summary:
            top = pains_out[0] if pains_out else None
            summary = (
                f"「{product}」共识别 {len(pains_out)} 个痛点，最突出为「{top.pain}」。"
                if top else f"「{product}」暂无明显痛点信号。"
            )
        return VOCOutput(
            product_name=product, country=country,
            pain_points=pains_out, strengths=strengths, summary=summary)
