"""Profit Agent —— 输入 / 输出 Schema。

所有金额单位为「单件美元（USD）」，由用户真实输入或经数据源（Excel / 供应链接口）提供。
本 Agent 只做确定性计算，不调用 LLM 编造数据。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProfitInput(BaseModel):
    """用户/数据源提供的成本与售价参数。"""
    product_name: str = Field(..., description="产品名称")
    country: str = Field("US", description="站点国家代码")
    platform: str = Field("amazon", description="平台：amazon / shopify / independent")

    selling_price: float = Field(..., gt=0, description="售价（单件，USD）")
    category: Optional[str] = Field(None, description="类目，用于销量预测的需求基准")
    competition_level: Optional[str] = Field(None, description="竞争强度 low/medium/high（可由竞品分析联动带入）")
    competitor_price: Optional[float] = Field(None, ge=0, description="竞品均价，用于价格竞争力测算")
    # 单件成本构成
    product_cost: float = Field(0.0, ge=0, description="产品成本（采购/制造，单件）")
    shipping_cost: float = Field(0.0, ge=0, description="头程物流到仓（单件）")
    referral_fee_rate: float = Field(0.15, ge=0, le=1, description="Amazon 佣金率（默认 15%）")
    fba_fee: float = Field(3.5, ge=0, description="FBA 履约费（单件固定，按尺寸分段）")
    ad_acos: float = Field(0.15, ge=0, le=1, description="广告 ACOS（广告费 / 销售额）")
    other_cost_per_unit: float = Field(0.0, ge=0, description="其他单件成本（包装/退款预留/耗材）")

    # 规模与投入
    monthly_units: Optional[int] = Field(None, ge=0, description="预期月销量；留空则由销量预测 Agent 估算")
    monthly_fixed_cost: float = Field(0.0, ge=0, description="月度固定成本（仓储/工具/人工）")
    initial_investment: float = Field(0.0, ge=0, description="首单/模具/备货投入（用于回本测算）")

    # 数据来源追踪
    cost_source: Optional[str] = Field("manual", description="manual / excel / supply_chain")
    product_id: Optional[str] = Field(None, description="产品空间 ID，用于回写联动")
    currency: str = Field("USD", description="币种")


class ProfitBreakdown(BaseModel):
    """单件利润拆解。"""
    selling_price: float
    product_cost: float
    shipping_cost: float
    referral_fee: float
    fba_fee: float
    amazon_fee: float          # = referral_fee + fba_fee
    ad_cost: float
    other_cost: float
    gross_profit: float        # 售价 - 产品 - 物流 - Amazon费
    net_profit: float          # 毛利 - 广告 - 其他
    net_margin: float          # 净利润 / 售价


class ProfitOutput(BaseModel):
    product_name: str
    country: str
    per_unit: ProfitBreakdown
    monthly_units: int
    monthly_gross_profit: float
    monthly_net_profit: float
    monthly_fixed_cost: float
    monthly_net_operating: float
    profitability_score: float
    recommendation: str        # invest / cautious / avoid
    recommendation_reason: str
    cost_source: str
