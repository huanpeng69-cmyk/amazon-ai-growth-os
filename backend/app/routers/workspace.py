"""产品空间（Workspace）API —— 跨模块共享上下文的单一数据源。

所有模块从这里读取「产品名 / 利基 / 类目 / 站点 / 平台 / 预算」等公共身份字段，
并把各自的产出回写到这里，从而：
  - 避免每个模块重复填写同一批基础信息；
  - 为下一轮「跨模块数据互相促进」沉淀统一的数据底座。

复用 lifecycle 的 GrowthProduct 作为载体（其本身即「增长 OS 控制塔」的实体）。
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..lifecycle.models import GrowthProduct, StageArtifact
from ..lifecycle.schemas import GrowthProductOut

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])

# 输入字段名 → GrowthProduct 属性名 的映射（用于把产品空间字段回填进各 Agent 入参）
FIELD_MAP = {
    "product_name": "name",
    "niche_keyword": "niche_keyword",
    "country": "country",
    "target_country": "country",
    "platform": "platform",
    "budget_usd": "budget_usd",
}


# ───────────────────────── 共享助手（供 agent 路由复用） ─────────────────────────
def load_product_for(db: Session, product_id: Optional[str]) -> Optional[GrowthProduct]:
    """解析目标产品：显式 product_id 优先；否则取最近更新（= 活动）的产品。"""
    if product_id:
        return db.query(GrowthProduct).filter(GrowthProduct.product_id == product_id).first()
    return (
        db.query(GrowthProduct)
        .order_by(GrowthProduct.updated_at.desc())
        .first()
    )


def fill_input(model: BaseModel, product: GrowthProduct, fields: list[str]) -> BaseModel:
    """用产品空间的公共字段，回填入参模型中为空（缺失）的字段。"""
    data = model.model_dump()
    for f in fields:
        if f in data and not data.get(f):
            attr = FIELD_MAP.get(f)
            if attr:
                data[f] = getattr(product, attr, None) or data[f]
    return type(model)(**data)


def store_module_output(db: Session, product: GrowthProduct, module: str,
                        output: dict, identity: Optional[dict] = None) -> None:
    """把某模块的产出落库到产品空间（StageArtifact），并同步最新身份字段。

    - output: Agent 的结构化产出（model_dump）。
    - identity: 本次请求里用户填写的身份字段，用于让产品空间与最新一次生成保持同步。
    任何异常都不应阻断主流程，故整体 try/except。
    """
    try:
        if identity:
            for inp_field, attr in FIELD_MAP.items():
                val = identity.get(inp_field)
                if val:
                    setattr(product, attr, val)
        db.add(product)

        stage = "mod_" + module
        art = db.query(StageArtifact).filter_by(product_fk=product.id, stage=stage).first()
        if not art:
            art = StageArtifact(product_fk=product.id, stage=stage)
            db.add(art)
        art.status, art.summary, art.data = "done", f"{module} 产出已存档", output
        db.commit()
    except Exception as e:  # 存档失败绝不阻断生成
        db.rollback()
        print(f"[workspace] store_module_output skipped for {module}: {e}")


# ───────────────────────── 请求契约 ─────────────────────────
class WorkspaceContext(BaseModel):
    product_id: Optional[str] = None
    force_create: bool = False
    name: Optional[str] = None
    niche_keyword: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None
    platform: Optional[str] = None
    budget_usd: Optional[int] = None


# ───────────────────────── 路由 ─────────────────────────
@router.get("")
def get_active(db: Session = Depends(get_db)):
    """返回当前活动产品（最近更新者）的上下文；无则返回 {active:null}。"""
    p = load_product_for(db, None)
    if not p:
        return {"active": None}
    return {"active": _to_out(p)}


@router.get("/products")
def list_products(db: Session = Depends(get_db)):
    """列出全部产品，供上下文条切换。"""
    return [_to_out(p) for p in
            db.query(GrowthProduct).order_by(GrowthProduct.updated_at.desc()).all()]


@router.post("/{product_id}/activate")
def activate(product_id: str, db: Session = Depends(get_db)):
    """将某产品设为活动（仅刷新 updated_at，不改动业务字段）。"""
    p = db.query(GrowthProduct).filter(GrowthProduct.product_id == product_id).first()
    if not p:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="product not found")
    from datetime import datetime
    p.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return _to_out(p)


@router.put("/context")
def upsert_context(body: WorkspaceContext, db: Session = Depends(get_db)):
    """upsert 共享上下文：指定 product_id 改之；否则改活动产品；都没有则新建。
    force_create=true 时永远新建一个产品（用于「＋新建产品」）。"""
    if body.force_create:
        p = None
    else:
        p = load_product_for(db, body.product_id)
    if not p:
        p = GrowthProduct(
            product_id=str(uuid.uuid4()),
            name=body.name or "未命名产品",
            niche_keyword=body.niche_keyword or "",
            category=body.category or "",
            country=body.country or "US",
            platform=body.platform or "amazon",
            budget_usd=body.budget_usd or 5000,
            current_stage="discover",
        )
        db.add(p)
    else:
        if body.name is not None:
            p.name = body.name
        if body.niche_keyword is not None:
            p.niche_keyword = body.niche_keyword
        if body.category is not None:
            p.category = body.category
        if body.country is not None:
            p.country = body.country
        if body.platform is not None:
            p.platform = body.platform
        if body.budget_usd is not None:
            p.budget_usd = body.budget_usd
    db.commit()
    db.refresh(p)
    return _to_out(p)


# ───────────────────────── 内部工具 ─────────────────────────
def _artifact_data(db: Session, product: GrowthProduct, module: str) -> Optional[dict]:
    """读取某模块在产品空间里已存档的产出（无则 None）。"""
    art = db.query(StageArtifact).filter_by(product_fk=product.id, stage="mod_" + module).first()
    return art.data if art else None


def build_linkage(db: Session, product: GrowthProduct) -> dict:
    """构建「跨模块互相促进」链路图。

    - upstream：已产生数据的上游模块（VOC / 竞品 / 市场）及其关键条目。
    - injections：下游模块（Listing / 视觉 / 广告）可直接复用的派生字段。
      这些派生值由上游产出转换而来（痛点→卖点/关键词、竞品软肋→差异化角度）。
    """
    arts = {m: _artifact_data(db, product, m)
            for m in ("voc", "competitor", "market", "listing", "visual", "image", "advertising")}

    upstream: list[dict] = []
    voc = arts["voc"]
    if voc:
        pts = voc.get("pain_points", [])
        upstream.append({
            "module": "voc", "label": "VOC 用户痛点", "count": len(pts),
            "summary": voc.get("summary", ""),
            "items": [{"pain": p.get("pain"), "fix": p.get("suggested_fix")} for p in pts[:6]],
        })
    comp = arts["competitor"]
    if comp:
        cs = comp.get("competitors", [])
        upstream.append({
            "module": "competitor", "label": "竞品分析", "count": len(cs),
            "summary": comp.get("summary", ""),
            "items": [{"name": c.get("name"), "weakness": c.get("weakness")} for c in cs[:4]],
        })
    mk = arts["market"]
    if mk:
        ops = mk.get("opportunities", [])
        upstream.append({
            "module": "market", "label": "蓝海市场", "count": len(ops),
            "summary": mk.get("summary", ""),
            "items": [{"name": o.get("product_name"), "niche": o.get("niche_keyword")} for o in ops[:4]],
        })

    injections: dict = {}
    if voc:
        pts = voc.get("pain_points", [])
        injections["listing"] = {
            "key_features": [p.get("suggested_fix") for p in pts if p.get("suggested_fix")],
        }
        injections["visual"] = {
            "selling_points": [f"针对「{p.get('pain')}」：{p.get('suggested_fix')}" for p in pts],
        }
        kw = [f"{product.name} {p.get('pain')}" for p in pts]
        if product.niche_keyword:
            kw.append(product.niche_keyword)
        injections["advertising"] = {"seed_keywords": kw}
    if comp:
        weak = [c.get("weakness") for c in comp.get("competitors", []) if c.get("weakness")]
        injections.setdefault("listing", {})["differentiation"] = weak
        injections.setdefault("visual", {})["angles"] = weak
        inj_ads = injections.setdefault("advertising", {})
        inj_ads.setdefault("seed_keywords", []).extend([f"{product.name} {w}" for w in weak])

    return {
        "product_id": product.product_id,
        "upstream": upstream,
        "injections": injections,
        "has_upstream": len(upstream) > 0,
    }


@router.get("/{product_id}/linkage")
def get_linkage(product_id: str, db: Session = Depends(get_db)):
    """返回该产品的跨模块联动图：哪些上游数据可复用、能灌入哪些下游模块。"""
    p = db.query(GrowthProduct).filter(GrowthProduct.product_id == product_id).first()
    if not p:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="product not found")
    return build_linkage(db, p)


def _to_out(p: GrowthProduct) -> GrowthProductOut:
    return GrowthProductOut(
        product_id=p.product_id, name=p.name, niche_keyword=p.niche_keyword,
        category=p.category, country=p.country, platform=p.platform,
        budget_usd=p.budget_usd, current_stage=p.current_stage,
        overall_health=0.0, stages=[], created_at=p.created_at, updated_at=p.updated_at,
    )
