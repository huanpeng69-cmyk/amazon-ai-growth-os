"""产品生命周期管理 API —— 增长操作系统控制塔。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..lifecycle.schemas import CreateProductRequest, GrowthProductOut
from ..lifecycle import service

router = APIRouter(prefix="/api/lifecycle", tags=["lifecycle"])


@router.post("", response_model=GrowthProductOut)
def create(req: CreateProductRequest, db: Session = Depends(get_db)):
    """新建一个被增长操作系统接管的产品（从「发现产品」阶段开始）。"""
    return service.create_product(req, db)


@router.get("", response_model=list[GrowthProductOut])
def list_all(db: Session = Depends(get_db)):
    """列出所有增长产品及其当前生命周期看板。"""
    return service.list_products(db)


@router.get("/{product_id}", response_model=GrowthProductOut)
def board(product_id: str, db: Session = Depends(get_db)):
    """获取单个产品的六阶段生命周期看板。"""
    out = service.get_board(product_id, db)
    if not out:
        raise HTTPException(status_code=404, detail="product not found")
    return out


@router.post("/{product_id}/advance", response_model=GrowthProductOut)
def advance(product_id: str, db: Session = Depends(get_db)):
    """推进当前阶段：调用对应 Agent 产出制品并评分，再进入下一阶段。"""
    out = service.advance(product_id, db)
    if not out:
        raise HTTPException(status_code=404, detail="product not found")
    return out


@router.get("/{product_id}/artifact/{stage}")
def artifact(product_id: str, stage: str, db: Session = Depends(get_db)):
    """获取某阶段已产出的结构化制品数据。"""
    data = service.get_artifact(product_id, stage, db)
    if data is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {"product_id": product_id, "stage": stage, "data": data}
