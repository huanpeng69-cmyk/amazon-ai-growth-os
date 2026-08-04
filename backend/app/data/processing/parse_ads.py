"""解析 ads_connector 原始响应 → AdData。"""
from __future__ import annotations

from typing import Any, Dict

from app.data.exceptions import DataNotFound
from app.data.schemas import AdData


def parse_ads(raw: Dict[str, Any]) -> AdData:
    ads = (raw.get("payload") or {}).get("ads")
    if not ads:
        raise DataNotFound("ads_connector 返回为空，无法解析广告数据")
    return AdData(
        acos=_f(ads.get("acos")),
        roas=_f(ads.get("roas")),
        ctr=_f(ads.get("ctr")),
        cvr=_f(ads.get("cvr")),
        spend=_f(ads.get("spend")),
        ad_sales=_f(ads.get("ad_sales")),
        orders=_i(ads.get("orders")),
        period_start=ads.get("period_start"),
        period_end=ads.get("period_end"),
    )


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
