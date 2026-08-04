"""解析 keyword_connector 原始响应 → KeywordData 列表。"""
from __future__ import annotations

from typing import Any, Dict, List

from app.data.exceptions import DataNotFound
from app.data.schemas import KeywordData


def parse_keywords(raw: Dict[str, Any]) -> List[KeywordData]:
    keywords = (raw.get("payload") or {}).get("keywords") or []
    if not keywords:
        raise DataNotFound("keyword_connector 返回为空，无法解析关键词")
    out: List[KeywordData] = []
    for k in keywords:
        out.append(KeywordData(
            keyword=(k.get("keyword") or "").strip(),
            search_volume=_i(k.get("search_volume")),
            competition=_f(k.get("competition")),
            cpc=_f(k.get("cpc")),
            trend=k.get("trend"),
        ))
    return out


def _f(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None
