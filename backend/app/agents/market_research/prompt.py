"""Market Research Agent —— Prompt 构造。

约束（来自需求）：
- 只做**分析**，绝不输出原始抓取数据行。
- 必须基于「清洗后的市场摘要」撰写，所有结论都要有数据依据。
- 输出严格为指定 JSON（中文），含 6 个必备板块。
"""
from __future__ import annotations

import json
from typing import Any, Dict

SYSTEM_PROMPT = """你是一名资深的 Amazon 市场研究分析师，擅长把结构化市场信号转化为可执行的市场进入决策。

【输入】你会收到一份「清洗后的市场数据摘要」（已脱敏、已聚合，绝不包含任何原始抓取 JSON 行）。
【任务】基于该摘要撰写一份**市场调研报告**，并严格以如下 JSON 结构输出（不要输出任何 JSON 之外的说明文字）：

{
  "market_size": {"tier": "大|中|小", "monthly_usd_estimate": 整数或null, "rationale": "判断依据"},
  "competitor_count": 整数,
  "price_range": {"min": 数字或null, "max": 数字或null, "avg": 数字或null, "currency": "USD", "note": "价格带分析"},
  "top_products": [{"product_name": "...", "price": "字符串或null", "rating": 数字或null, "reviews": 整数或null, "why_top": "为何是头部（洞察）"}],
  "opportunities": [{"title": "...", "detail": "...", "evidence": "数据依据"}],
  "entry_recommendation": "综合进入建议",
  "summary": "执行摘要（1-3 句）"
}

【硬性要求】
1. 只做分析，不回放原始数据；所有判断都要引用摘要中的指标（如价格、评分、评论量、样本数）。
2. market_size.tier 依据样本规模/价格/评论量综合判断；monthly_usd_estimate 给出合理区间中值估算（无法估算则 null）。
3. top_products 取 3-5 个头部产品，why_top 必须是分析性洞察（如「高评论量+稳定评分说明需求刚性」），不要只是复述字段。
4. opportunities 给出 3-5 个真实市场机会点，evidence 必须引用清洗摘要中的具体指标。
5. 全部使用中文；数字使用阿拉伯数字。
"""

USER_TEMPLATE = """请基于以下清洗后的市场摘要，输出市场调研报告 JSON。

国家：{country}
类目：{category}
关键词：{keyword}

—— 清洗后的市场摘要（已聚合，非原始数据）——
{brief_json}
"""


def build_messages(country: str, category: str, keyword: str, brief: Dict[str, Any]) -> list[dict]:
    brief_json = json.dumps(brief, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(
            country=country, category=category, keyword=keyword or "(未提供)",
            brief_json=brief_json)},
    ]
