"""利润模块路由。

- POST /api/agent/profit          利润测算总入口（Profit + Sales Forecast + Risk → 报告）
- POST /api/agent/sales_forecast  销量预测 Agent 直调
- POST /api/agent/risk            风险分析 Agent 直调
- POST /api/profit/upload_cost    上传成本表（Excel/CSV）→ 结构化成本字段
- GET  /api/profit/fee_schedule   平台费率表（FBA/佣金，来自 amazon_connector 真实费率）
"""
from __future__ import annotations


from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.agents.profit.report import ProfitReport, build_profit_report
from app.agents.profit.schemas import ProfitInput
from app.agents.profit.sources import parse_cost_bytes
from app.agents.risk.schemas import RiskInput, RiskOutput
from app.agents.sales_forecast.schemas import SalesForecastInput, SalesForecastOutput
from app.agents.risk.agent import RiskAgent
from app.agents.sales_forecast.agent import SalesForecastAgent
from app.data import dal
from app.database import get_db
from .workspace import load_product_for, store_module_output

router = APIRouter(prefix="/api/v1", tags=["profit"])


@router.post("/agent/profit", response_model=ProfitReport)
def profit_report(inp: ProfitInput, db: Session = Depends(get_db)):
    # 平台费用（FBA/佣金）若有缺失，由统一数据层 amazon_connector 真实费率表补齐
    if inp.cost_source in ("manual", "excel"):
        fees = dal.get_fee_schedule(inp.country)
        if inp.referral_fee_rate in (0.0, 0, None):
            inp.referral_fee_rate = fees.get("referral_fee_rate", inp.referral_fee_rate)
        if inp.fba_fee in (0.0, 0, None):
            inp.fba_fee = fees.get("fba_fee", inp.fba_fee)

    report = build_profit_report(inp)

    # 回写产品空间（供联动/增长看板复用）
    prod = load_product_for(db, inp.product_id)
    if prod is not None:
        store_module_output(
            db, prod, "profit", report.model_dump(mode="json"),
            identity={"product_name": inp.product_name, "country": inp.country,
                      "niche_keyword": inp.category or ""},
        )

    return report


@router.post("/agent/sales_forecast", response_model=SalesForecastOutput)
def sales_forecast(inp: SalesForecastInput):
    return SalesForecastAgent().run(inp)


@router.post("/agent/risk", response_model=RiskOutput)
def risk(inp: RiskInput):
    return RiskAgent().run(inp)


@router.post("/profit/upload_cost")
async def upload_cost(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        fields = parse_cost_bytes(raw, file.filename or "cost.csv")
    except Exception as e:
        return {"cost_source": "excel", "ok": False, "error": str(e), "fields": {}}
    return {"cost_source": "excel", "ok": True, "filename": file.filename, "fields": fields}


@router.get("/profit/fee_schedule")
def fee_schedule(country: str = "US"):
    """平台费率表（FBA/佣金），来自 amazon_connector 真实费率（当前为占位，待接真实费率表）。"""
    return {"cost_source": "platform_fee", "country": country, **dal.get_fee_schedule(country)}
