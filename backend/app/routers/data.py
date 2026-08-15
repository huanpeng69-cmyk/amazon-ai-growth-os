"""数据层状态与溯源 API。

- GET /api/data/connectors   ：5 个 Connector 的健康探针（模式 / 凭证 / fixture / 真实可用性）+ DB 缓存统计。
- GET /api/data/provenance   ：给定 Connector 的数据溯源徽标信息（来源 fixture/live + 最近回源时间）。

这些端点让「统一数据层」可视化：用户在设置页能看到每个 Connector 是否就绪，
在 Agent 报告页能看到数据到底来自真实样本还是真实 API、何时拉取的。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config_store import get_connector_config
from app.data.connectors import ConnectorRegistry
from app.data.exceptions import ConnectorNotConfigured, DataNotFound, FixtureMissing
from app.data.models import (
    AdRecord,
    ImageRecord,
    KeywordRecord,
    ProductRecord,
    RawFetch,
    ReviewRecord,
)
from app.database import get_db

router = APIRouter(prefix="/api/data", tags=["data"])

# 探测用查询：尽量命中各 fixture 中真实存在的样本键
_PROBES = {
    "amazon": {"keyword": "cat water fountain", "country": "US"},
    "review": {"asin": "B09EXAMPLE02", "country": "US"},
    "keyword": {"seed_keyword": "cat water fountain", "country": "US"},
    "ads": {"asin": "B09EXAMPLE02", "country": "US"},
    "image": {"asin": "B09EXAMPLE02", "query": "cat water fountain", "kind": "reference"},
}


def _resolved_mode(cfg: dict) -> str:
    mode = (cfg.get("mode") or "auto").lower()
    if mode == "live":
        return "live"
    if mode == "fixture":
        return "fixture"
    # auto：有凭证即视为可走 live（但 LiveAdapter 可能尚未实现 → 由 fetch 降级 fixture）
    return "live" if (cfg.get("api_key") or cfg.get("endpoint")) else "fixture"


def _probe(name: str) -> dict:
    cfg = get_connector_config(name)
    has_key = bool(cfg.get("api_key"))
    resolved = _resolved_mode(cfg)
    try:
        c = ConnectorRegistry.get(name, cfg)
    except Exception as e:  # noqa: BLE001
        return {
            "name": name, "mode": cfg.get("mode", "auto"), "resolved_mode": resolved,
            "has_key": has_key, "status": "error", "source": None,
            "detail": f"注册失败：{e}", "fixture_present": False,
        }
    fixture_present = bool(getattr(c, "fixture_path", None) and Path(c.fixture_path).exists())
    try:
        raw = c.fetch(_PROBES.get(name, {}))
        src = getattr(raw, "source", "fixture")
        if resolved == "live" and src != "live":
            status, detail = "warn", "Live 未就绪，已自动降级 fixture"
        elif src == "live":
            status, detail = "ok", "Live 已连接"
        else:
            status, detail = "ok", "真实样本（fixture）已加载"
    except ConnectorNotConfigured:
        status, detail, src = "warn", "Live 未就绪（缺凭证 / 未实现），已降级 fixture", "fixture"
    except DataNotFound:
        status, detail, src = "warn", "fixture 无匹配样本（可换查询词）", "fixture"
    except FixtureMissing:
        status, detail, src = "error", "fixture 样本文件缺失", None
    except Exception as e:  # noqa: BLE001
        status, detail, src = "error", f"探测异常：{str(e)[:160]}", None
    return {
        "name": name, "mode": cfg.get("mode", "auto"), "resolved_mode": resolved,
        "has_key": has_key, "status": status, "source": src,
        "detail": detail, "fixture_present": fixture_present,
    }


@router.get("/connectors")
def list_connectors(db: Session = Depends(get_db)):
    connectors = [_probe(n) for n in ConnectorRegistry.list()]
    stats = {}
    for label, model in (
        ("products", ProductRecord),
        ("reviews", ReviewRecord),
        ("keyword_metrics", KeywordRecord),
        ("ad_metrics", AdRecord),
        ("image_assets", ImageRecord),
        ("raw_fetches", RawFetch),
    ):
        try:
            stats[label] = db.query(model).count()
        except Exception:  # noqa: BLE001  -- 表尚未创建时返回 0，避免端点 500
            stats[label] = 0
    return {"connectors": connectors, "stats": stats}


@router.get("/provenance")
def provenance(
    connectors: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """数据溯源徽标：每个 Connector 最近一次真实回源（写入领域表）的时间与来源。

    以领域表（products/reviews/keyword_metrics/ad_metrics/image_assets）的
    fetched_at / source 为准——这些字段在 DAL 每次真实 fetch 后落库，比 raw_fetches
    更可靠（DAL 常命中缓存，不会再写 raw_fetches，但领域表的 fetched_at 始终保留）。

    connectors 为逗号分隔字符串（如 "amazon,review,keyword"），便于前端单参数传递。
    """
    _MODEL_BY_CONNECTOR = {
        "amazon": ProductRecord,
        "review": ReviewRecord,
        "keyword": KeywordRecord,
        "ads": AdRecord,
        "image": ImageRecord,
    }
    names = [c.strip() for c in (connectors or "").split(",") if c.strip()] or ConnectorRegistry.list()
    out = []
    for name in names:
        cfg = get_connector_config(name)
        resolved = _resolved_mode(cfg)
        model = _MODEL_BY_CONNECTOR.get(name)
        rec = None
        if model is not None:
            try:
                rec = db.query(model).order_by(desc(model.fetched_at)).first()
            except Exception:  # noqa: BLE001
                rec = None
        if rec is not None and getattr(rec, "fetched_at", None):
            out.append({
                "connector": name,
                "source": getattr(rec, "source", "fixture") or "fixture",
                "mode": cfg.get("mode", "auto"),
                "status": "fetched",
                "fetched_at": rec.fetched_at.isoformat(),
            })
        else:
            out.append({
                "connector": name,
                "source": resolved,
                "mode": cfg.get("mode", "auto"),
                "status": "pending",
                "fetched_at": None,
            })
    return {"provenance": out}
