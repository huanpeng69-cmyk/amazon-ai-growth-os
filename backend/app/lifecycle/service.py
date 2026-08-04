"""Lifecycle 编排服务 —— 六阶段增长管道的控制塔。

每个阶段调用对应 Agent 产出制品并评分，产品沿管道逐步推进；
overall_health 为各阶段已完成制品分数的均值。
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from ..lifecycle.models import GrowthProduct, StageArtifact
from ..lifecycle.schemas import CreateProductRequest, GrowthProductOut, StageInfo

# 六阶段顺序（即用户要求的完整管道）
STAGE_ORDER = ["discover", "analyze", "design", "build", "advertise", "optimize"]
STAGE_LABELS = {
    "discover": "发现产品",
    "analyze": "分析机会",
    "design": "设计产品",
    "build": "生成页面",
    "advertise": "投放广告",
    "optimize": "优化增长",
}


# ───────────────────────── 阶段执行 ─────────────────────────
def _run_stage(stage: str, p: GrowthProduct):
    """执行某一阶段，返回 (score:float, summary:str, data:dict)。"""
    if stage == "discover":
        from ..agents.market.agent import MarketAgent
        from ..agents.market.schemas import MarketInput
        out = MarketAgent().run(MarketInput(
            country=p.country, category=p.niche_keyword or p.name, budget_usd=p.budget_usd))
        top = out.opportunities[0]
        data = {
            "product_name": top.product_name,
            "market_size_monthly_usd": top.market_size_monthly_usd,
            "growth_yoy": top.market_size_growth_yoy,
            "competition_level": top.competition_level,
            "opportunity_score": top.opportunity_score,
        }
        return (top.opportunity_score,
                f"扫描到「{top.product_name}」等 {len(out.opportunities)} 个机会，"
                f"最优机会评分 {top.opportunity_score}（{top.competition_level} 竞争）。", data)

    if stage == "analyze":
        from ..agents.voc.agent import VOCAgent
        from ..agents.voc.schemas import VOCInput
        out = VOCAgent().run(VOCInput(product_name=p.niche_keyword or p.name, country=p.country))
        pains = [{"pain": x.pain, "severity": x.severity, "evidence": x.evidence,
                  "suggested_fix": x.suggested_fix} for x in out.pain_points]
        avg_sev = sum(x["severity"] for x in pains) / len(pains) if pains else 0
        score = round(min(100.0, 50 + 10 * len(pains) + (avg_sev - 50) * 0.3), 1) if pains else 50.0
        return (score, out.summary,
                {"summary": out.summary, "pain_points": pains, "strengths": out.strengths})

    if stage == "design":
        from ..agents.product.agent import ProductAgent
        from ..agents.product.schemas import ProductInput
        out = ProductAgent().run(ProductInput(
            niche_keyword=p.niche_keyword or p.name, country=p.country, budget_usd=p.budget_usd))
        return (out.opportunity_score,
                f"产品机会判断：{out.verdict}（评分 {out.opportunity_score}）。"
                f"推荐定位：{out.recommended_positioning}",
                {"verdict": out.verdict, "opportunity_score": out.opportunity_score,
                 "reasons": out.reasons, "recommended_positioning": out.recommended_positioning})

    if stage == "build":
        from ..agents.listing.agent import ListingAgent
        from ..agents.listing.schemas import ListingInput
        out = ListingAgent().run(ListingInput(
            product_name=p.name, niche_keyword=p.niche_keyword, tone="专业可信"))
        return (out.completeness_score,
                f"已生成 Listing（完整度 {out.completeness_score}）：标题 {len(out.title)} 字符、"
                f"{len(out.bullet_points)} 条五点、{len(out.search_terms)} 个搜索词、{len(out.image_plan)} 张图。",
                {"title": out.title, "bullet_points": out.bullet_points,
                 "description": out.description, "search_terms": out.search_terms,
                 "image_plan": [img.model_dump() for img in out.image_plan],
                 "compliance_notes": out.compliance_notes})

    if stage == "advertise":
        from ..agents.advertising.agent import AdvertisingAgent
        from ..agents.advertising.schemas import AdvertisingInput
        out = AdvertisingAgent().run(AdvertisingInput(
            product_name=p.name, niche_keyword=p.niche_keyword,
            country=p.country, budget_usd=p.budget_usd))
        return (out.efficiency_score, out.summary,
                {"summary": out.summary,
                 "metrics": [m.model_dump() for m in out.metrics],
                 "campaign_actions": [a.model_dump() for a in out.campaign_actions],
                 "budget_recommendation": out.budget_recommendation})

    if stage == "optimize":
        prior = {a.stage: a.score for a in p.artifacts if a.status == "done"}
        health = round(sum(prior.values()) / len(prior), 1) if prior else 0.0
        actions = []
        if prior.get("advertise", 100) < 70:
            actions.append("广告效率偏低：先否定低效词、把自动广告迁移到手动精准组压低 ACOS。")
        if prior.get("build", 100) < 80:
            actions.append("Listing 完整度不足：补齐五点、增加场景图与 A+ 内容提升转化。")
        if prior.get("discover", 100) < 60:
            actions.append("市场机会一般：考虑换利基或用差异化卖点重新定位。")
        if not actions:
            actions.append("各阶段健康度良好，建议阶梯放量并持续监控 ACOS 与评分。")
        return (health, f"综合健康度 {health}。建议：{actions[0]}",
                {"health": health, "actions": actions, "stage_scores": prior})

    raise ValueError(f"unknown stage: {stage}")


# ───────────────────────── 对外服务 ─────────────────────────
def create_product(req: CreateProductRequest, db: Session) -> GrowthProductOut:
    p = GrowthProduct(
        product_id=str(uuid.uuid4()), name=req.name, niche_keyword=req.niche_keyword,
        category=req.category or "", country=req.country, platform=req.platform or "amazon",
        budget_usd=req.budget_usd, current_stage="discover")
    db.add(p)
    db.commit()
    db.refresh(p)
    return get_board(p.product_id, db)


def get_board(product_id: str, db: Session) -> Optional[GrowthProductOut]:
    p = db.query(GrowthProduct).filter(GrowthProduct.product_id == product_id).first()
    if not p:
        return None
    arts = {a.stage: a for a in p.artifacts}
    stages: list[StageInfo] = []
    for s in STAGE_ORDER:
        art = arts.get(s)
        if art and art.status == "done":
            stages.append(StageInfo(stage=s, label=STAGE_LABELS[s], status="done",
                                    score=art.score, summary=art.summary))
        elif s == p.current_stage:
            stages.append(StageInfo(stage=s, label=STAGE_LABELS[s], status="current"))
        else:
            stages.append(StageInfo(stage=s, label=STAGE_LABELS[s], status="locked"))
    done_scores = [a.score for a in p.artifacts if a.status == "done"]
    health = round(sum(done_scores) / len(done_scores), 1) if done_scores else 0.0
    return GrowthProductOut(
        product_id=p.product_id, name=p.name, niche_keyword=p.niche_keyword,
        category=p.category, country=p.country, platform=p.platform,
        budget_usd=p.budget_usd, current_stage=p.current_stage,
        overall_health=health, stages=stages, created_at=p.created_at, updated_at=p.updated_at)


def list_products(db: Session) -> list[GrowthProductOut]:
    return [get_board(p.product_id, db) for p in
            db.query(GrowthProduct).order_by(GrowthProduct.created_at.desc()).all()]


def advance(product_id: str, db: Session) -> Optional[GrowthProductOut]:
    p = db.query(GrowthProduct).filter(GrowthProduct.product_id == product_id).first()
    if not p:
        return None
    score, summary, data = _run_stage(p.current_stage, p)

    art = db.query(StageArtifact).filter_by(product_fk=p.id, stage=p.current_stage).first()
    if not art:
        art = StageArtifact(product_fk=p.id, stage=p.current_stage)
        db.add(art)
    art.status, art.score, art.summary, art.data = "done", score, summary, data
    db.commit()

    idx = STAGE_ORDER.index(p.current_stage)
    if idx < len(STAGE_ORDER) - 1:
        p.current_stage = STAGE_ORDER[idx + 1]
        db.commit()
        db.refresh(p)
    return get_board(p.product_id, db)


def get_artifact(product_id: str, stage: str, db: Session):
    p = db.query(GrowthProduct).filter(GrowthProduct.product_id == product_id).first()
    if not p:
        return None
    art = db.query(StageArtifact).filter_by(product_fk=p.id, stage=stage).first()
    return art.data if art else None
