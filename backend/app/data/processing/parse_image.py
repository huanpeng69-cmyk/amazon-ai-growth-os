"""解析 image_connector 原始响应 → ImageData 列表。"""
from __future__ import annotations

from typing import Any, Dict, List

from app.data.exceptions import DataNotFound
from app.data.schemas import ImageData


def parse_images(raw: Dict[str, Any]) -> List[ImageData]:
    images = (raw.get("payload") or {}).get("images") or []
    if not images:
        raise DataNotFound("image_connector 返回为空，无法解析图片")
    out: List[ImageData] = []
    for img in images:
        out.append(ImageData(
            url=(img.get("url") or "").strip(),
            width=_i(img.get("width")),
            height=_i(img.get("height")),
            kind=img.get("kind") or "reference",
            source=img.get("source") or "",
        ))
    return out


def _i(v):
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None
