"""蓝海挖掘 API 路由（Market Agent 驱动）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..agents.market.agent import MarketAgent
from ..agents.market.schemas import MarketInput
from ..database import get_db
from ..routers.workspace import load_product_for, store_module_output
from ..schemas import BlueOceanRequest, BlueOceanResult, PainPoint, ProductOpportunityOut

router = APIRouter(prefix="/api/blue-ocean", tags=["blue-ocean"])


def _persist(db: Session, output) -> models.ResearchTask:
    task = models.ResearchTask(
        task_id=str(uuid.uuid4()), country=output.country, category=output.category,
        budget_usd=output.budget_usd, status="done", completed_at=datetime.now(timezone.utc))
    db.add(task)
    db.commit()
    db.refresh(task)
    for o in output.opportunities:
        db.add(models.ProductOpportunity(
            task_id_fk=task.id, rank=o.rank, product_name=o.product_name,
            niche_keyword=o.niche_keyword, market_size_monthly_usd=o.market_size_monthly_usd,
            market_size_growth_yoy=o.market_size_growth_yoy, competition_level=o.competition_level,
            competition_score=o.competition_score, demand_score=o.demand_score,
            pain_severity_score=o.pain_severity_score, budget_fit_score=o.budget_fit_score,
            top_pain_points=[p.model_dump() for p in o.top_pain_points],
            opportunity_score=o.opportunity_score, entry_recommendation=o.entry_recommendation,
            source_signals={}))
    db.commit()
    db.refresh(task)
    return task


def _to_result(task: models.ResearchTask) -> BlueOceanResult:
    products = [
        ProductOpportunityOut(
            rank=o.rank, product_name=o.product_name, niche_keyword=o.niche_keyword,
            market_size_monthly_usd=o.market_size_monthly_usd, market_size_growth_yoy=o.market_size_growth_yoy,
            competition_level=o.competition_level, competition_score=o.competition_score,
            demand_score=o.demand_score, pain_severity_score=o.pain_severity_score,
            budget_fit_score=o.budget_fit_score,
            top_pain_points=[PainPoint(**pp) for pp in o.top_pain_points],
            opportunity_score=o.opportunity_score, entry_recommendation=o.entry_recommendation)
        for o in task.opportunities
    ]
    return BlueOceanResult(
        task_id=task.task_id, country=task.country, category=task.category,
        budget_usd=task.budget_usd, status=task.status, products=products,
        created_at=task.created_at, completed_at=task.completed_at)


@router.post("/research", response_model=BlueOceanResult)
def research(req: BlueOceanRequest, db: Session = Depends(get_db)) -> BlueOceanResult:
    """提交一次蓝海挖掘：国家 + 类目 + 预算 → Top10 潜力产品（由 Market Agent 计算并落库）。

    若携带 product_id，则把蓝海机会（含痛点与利基词）回写产品空间（mod_market），
    供下游模块在联动时复用。
    """
    output = MarketAgent().run(MarketInput(country=req.country, category=req.category, budget_usd=req.budget_usd))
    task = _persist(db, output)
    if req.product_id:
        prod = load_product_for(db, req.product_id)
        if prod:
            market_payload = {
                "country": output.country,
                "category": output.category,
                "summary": f"蓝海挖掘：{output.category}（{output.country}）命中 {len(output.opportunities)} 个潜力机会。",
                "opportunities": [
                    {
                        "product_name": o.product_name,
                        "niche_keyword": o.niche_keyword,
                        "opportunity_score": o.opportunity_score,
                        "top_pain_points": [p.model_dump() for p in o.top_pain_points],
                    }
                    for o in output.opportunities
                ],
            }
            store_module_output(db, prod, "market", market_payload,
                                identity={"niche_keyword": req.category, "country": req.country})
    return _to_result(task)


@router.get("/tasks/{task_id}", response_model=BlueOceanResult)
def get_task(task_id: str, db: Session = Depends(get_db)) -> BlueOceanResult:
    task = db.query(models.ResearchTask).filter(models.ResearchTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return _to_result(task)
