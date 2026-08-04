"""解析 amazon_connector 原始响应 → ProductData 列表。"""
from __future__ import annotations

from typing import Any, Dict, List

from app.data.exceptions import DataNotFound
from app.data.schemas import ProductData


def parse_products(raw: Dict[str, Any]) -> List[ProductData]:
    products = (raw.get("payload") or {}).get("products") or []
    if not products:
        raise DataNotFound("amazon_connector 返回为空，无法解析商品")
    out: List[ProductData] = []
    for p in products:
        out.append(ProductData(
            asin=p.get("asin"),
            country=raw.get("payload", {}).get("country") or raw.get("query", {}).get("country") or "US",
            title=(p.get("title") or "").strip(),
            price=_f(p.get("price")),
            bsr=_i(p.get("bsr")),
            est_monthly_sales=_i(p.get("est_monthly_sales")),
            sellers=_i(p.get("sellers")),
            rating=_f(p.get("rating")),
            review_count=_i(p.get("review_count")),
            category=p.get("category"),
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
