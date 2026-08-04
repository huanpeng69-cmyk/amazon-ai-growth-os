"""解析 review_connector 原始响应 → ReviewItem 列表。"""
from __future__ import annotations

from typing import Any, Dict, List

from app.data.exceptions import DataNotFound
from app.data.schemas import ReviewItem


def parse_reviews(raw: Dict[str, Any]) -> List[ReviewItem]:
    reviews = (raw.get("payload") or {}).get("reviews") or []
    if not reviews:
        raise DataNotFound("review_connector 返回为空，无法解析评论")
    out: List[ReviewItem] = []
    for r in reviews:
        out.append(ReviewItem(
            rating=float(r.get("rating") or 0.0),
            body=(r.get("body") or "").strip(),
            is_vp=bool(r.get("is_vp", False)),
            reviewed_at=r.get("reviewed_at"),
            pain_keywords=list(r.get("pain_keywords") or []),
        ))
    return out
