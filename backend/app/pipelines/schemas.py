"""多 Agent 流水线 —— 输入/输出 Schema。

流水线：市场调研 → 产品机会判断 → Listing 生成（带状态传递）。
设计要点：
- 顶层输入驱动每一步；上游产物作为「富化」喂给下游（不硬依赖）。
- 任意一步失败不影响下游（诚实降级）：记录错误后继续，最终报告哪些步成功。
"""
from typing import List, Optional

from pydantic import BaseModel, Field

from app.agents.listing.schemas import ListingOutput
from app.agents.market_research.schemas import MarketResearchReport
from app.agents.product.schemas import ProductOutput


class PipelineInput(BaseModel):
    country: str = Field("US", description="Amazon 站点国家代码")
    category: str = Field(..., description="市场类目，如 Pets / Kitchen（市场调研与产品判断都依赖）")
    keyword: str = Field("", description="细分关键词（与类目互补）")
    budget_usd: int = Field(5000, gt=0, description="入市预算（美元），喂给产品机会判断")
    product_name: Optional[str] = Field(None, description="产品名称；留空则由 keyword/category 推导")
    tone: str = Field("专业可信", description="Listing 文案语气")
    language: str = Field("en", description="Listing 输出语言")


class PipelineResult(BaseModel):
    country: str
    category: str
    keyword: str
    market_report: Optional[MarketResearchReport] = None
    product_result: Optional[ProductOutput] = None
    listing_result: Optional[ListingOutput] = None
    errors: List[str] = Field(default_factory=list, description="各步失败记录（空=全成功）")
