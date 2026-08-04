"""Supervisor Agent —— 执行器（意图判断 + 参数抽取 + 派发）。

演示用确定性路由（无 LLM 依赖、可复现）；生产可替换为 LLM 分类调用。
"""
from __future__ import annotations

import re

from app.agents.supervisor.schemas import AgentRunResult, SupervisorInput, SupervisorPlan
from app.agents.supervisor.tools import SUPERVISOR_TOOLS

COUNTRY_ZH = {"美国": "US", "德国": "DE", "日本": "JP", "英国": "UK",
              "法国": "FR", "加拿大": "CA", "澳大利亚": "AU"}
COUNTRY_RE = re.compile(r"\b(US|DE|JP|UK|FR|CA|AU|IT|ES|MX)\b")

CATEGORY_ZH = {"厨房": "Kitchen", "健身": "Fitness", "宠物": "Pets", "婴儿": "Baby",
               "户外": "Outdoor", "电子": "Electronics", "美妆": "Beauty", "办公": "Office",
               "园艺": "Garden", "旅行": "Travel", "家居": "Home", "玩具": "Toys"}
CATEGORY_EN = ["kitchen", "fitness", "pets", "baby", "outdoor", "electronics",
               "beauty", "office", "garden", "travel", "home", "toys"]

INTENT_KW = {
    "competitor": ["竞品", "对手", "竞品分析", "竞争分析", "competitor", "competitors"],
    "voc": ["评论", "评价", "反馈", "痛点", "用户声音", "voc", "reviews", "review"],
    "product": ["机会判断", "产品机会", "值不值得", "产品定位", "该不该做", "是否值得",
                "product opportunity"],
    "listing": ["listing", "标题", "五点", "详情页", "生成页面", "文案", "写listing",
                "listing生成", "生成 listing", "商品页"],
    "image": ["图片", "主图", "附图", "图像", "配图", "视觉", "产品图", "场景图",
              "generate image", "image", "图方案"],
    "visual": ["视觉工厂", "商品视觉", "图片方案", "主图策略", "图片策略", "7张图",
               "视觉策略", "visual factory", "visual strategy", "商品图方案", "图片规划"],
    "advertising": ["广告", "投广", "acos", "roas", "ppc", "推广", "投放", "ads",
                    "广告分析", "campaign", "广告优化"],
    "lifecycle": ["生命周期", "增长看板", "我的产品", "产品管理", "看板", "lifecycle",
                  "growth board", "增长操作系统"],
    "market": ["蓝海", "市场", "挖掘", "选品", "潜力", "机会", "找产品", "选个品",
               "market", "niche", "blue ocean", "opportunit"],
    "market_research": ["市场调研", "市场研究", "市场分析", "行业分析", "行业调研",
                        "市场报告", "调研", "行业研究", "market research",
                        "market analysis", "market research report"],
}

BUDGET_RE = re.compile(r"(\d[\d,]*)\s*(?:美元|美金|usd|\$|刀)?")

# 意图判断顺序：越具体越靠前
_INTENT_ORDER = ["competitor", "voc", "product", "listing", "visual", "image",
                 "advertising", "lifecycle", "market_research", "market"]


def _detect_country(q: str) -> str:
    for zh, code in COUNTRY_ZH.items():
        if zh in q:
            return code
    m = COUNTRY_RE.search(q)
    return m.group(1) if m else "US"


def _detect_category(q: str) -> str | None:
    for zh, en in CATEGORY_ZH.items():
        if zh in q:
            return en
    low = q.lower()
    for en in CATEGORY_EN:
        if en in low:
            return en.title()
    return None


def _detect_budget(q: str) -> int:
    m = BUDGET_RE.search(q)
    if m:
        return int(m.group(1).replace(",", ""))
    return 5000


def _detect_intent(q: str) -> str:
    low = q.lower()
    for intent in _INTENT_ORDER:
        if any(kw.lower() in low for kw in INTENT_KW[intent]):
            return intent
    return "unknown"


def _detect_product(q: str) -> str | None:
    """从语句中提取产品名（用于 listing / image / advertising 意图）。"""
    s = q
    # 去掉已知动作后缀
    for suf in ["的listing", "的标题", "的详情页", "的文案", "的商品页", "的图片", "的附图",
                "的图", "的视觉", "的产品图", "的场景图", "的生成图", "的广告", "的推广",
                "的视觉方案", "做商品视觉方案", "商品视觉方案", "视觉方案", "图片方案",
                "图片规划", "主图策略", "图片策略", "做视觉",
                "生成listing", "生成 listing", "写listing", " listing", " listing生成",
                "生成图片", "生成 图片", "生成图像", "图像", "产品图", "分析广告", "的广告分析"]:
        if suf in s.lower():
            s = s.lower().replace(suf, "")
            break
    # 去掉尾部「定位 / 面向 / 针对」等定位从句（避免污染产品名）
    for sep in ["，定位", "定位", "，面向", "面向", "，针对", "针对"]:
        idx = s.find(sep)
        if idx > 0:
            s = s[:idx]
            break
    # 去掉前导动词
    for pre in ["帮我", "请", "麻烦", "我想", "我要", "生成", "写", "做", "为", "给",
                "分析", "看看", "研究", "设计", "拍", "制作", "想", "需要"]:
        if s.startswith(pre):
            s = s[len(pre):]
    s = s.lstrip("一下我你请帮们想如果要可的").strip()
    s = s.strip("，,。. ")
    return s if len(s) >= 2 else None


def _fallback_niche(query: str) -> str | None:
    """当未识别到已知类目时，从语句中提取利基/产品短语。"""
    s = query
    for pre in ["帮我", "请", "麻烦", "我想", "我要", "分析一下", "分析", "看看", "研究一下",
                "研究", "评估一下", "评估", "判断一下", "判断", "对比一下", "对比",
                "做一下", "做", "关于", "找", "挖掘"]:
        if s.startswith(pre):
            s = s[len(pre):]
    s = s.lstrip("一下我你请帮们想如果要可")
    for suf in ["的竞品分析", "的竞品", "竞品分析", "竞品", "的用户评论痛点", "用户评论痛点",
                "的评论痛点", "评论痛点", "的评论", "的痛点", "的反馈", "的", "吧", "呢", "？", "?"]:
        idx = s.find(suf)
        if idx != -1:
            s = s[:idx]
            break
    s = s.strip().strip("，,。. ")
    return s if len(s) >= 2 else None


class SupervisorAgent:
    name = "supervisor"
    description = "总控 Agent：意图判断 + 参数抽取 + 派发专家 Agent"

    def plan(self, query: str) -> SupervisorPlan:
        intent = _detect_intent(query)
        country = _detect_country(query)
        category = _detect_category(query)
        budget = _detect_budget(query)

        if intent == "unknown":
            return SupervisorPlan(
                intent="unknown", routed_agents=[],
                reason="未能识别意图，需追问用户想要市场挖掘 / 竞品分析 / VOC / 产品机会判断 / Listing / 图片 / 广告 / 生命周期。",
                params={})

        # 生命周期：导航到看板（由前端接管），无需派发专家 Agent
        if intent == "lifecycle":
            return SupervisorPlan(intent=intent, routed_agents=[],
                                  reason="识别为产品生命周期管理，导航到增长看板。",
                                  params={"country": country})

        # 商品视觉：导航到视觉工厂（表单驱动 /api/agent/visual），不在此直接出图
        if intent == "visual":
            prod = _detect_product(query)
            return SupervisorPlan(intent=intent, routed_agents=[],
                                  reason="识别为商品视觉需求，导航到 AI 商品视觉工厂。",
                                  params={"country": country,
                                          "product_name": prod or "",
                                          "niche_keyword": category or prod or ""})

        params: dict = {"country": country}
        if intent == "market_research":
            category = _detect_category(query)
            keyword = _fallback_niche(query)
            if not category and not keyword:
                return SupervisorPlan(intent=intent, routed_agents=[],
                                      reason="缺少类目或关键词，需追问。",
                                      params={"country": country})
            category = category or keyword
            keyword = keyword or category
            return SupervisorPlan(
                intent=intent, routed_agents=[intent],
                reason=f"识别为市场调研（Bright Data 取数 + AI 分析）：{country}/{category}/关键词={keyword}",
                params={"country": country, "category": category, "keyword": keyword})

        if intent == "market":
            if not category:
                return SupervisorPlan(intent=intent, routed_agents=[],
                                      reason="缺少类目参数，需追问。",
                                      params={"country": country, "budget_usd": budget})
            params.update({"category": category, "budget_usd": budget, "top_n": 10})
            reason = f"识别为蓝海市场挖掘：{country}/{category}/预算${budget}"
        elif intent in ("listing", "image", "advertising"):
            prod = _detect_product(query)
            if not prod:
                return SupervisorPlan(intent=intent, routed_agents=[],
                                      reason="缺少产品名称，需追问。",
                                      params={"country": country})
            niche = category or prod
            params.update({"product_name": prod, "niche_keyword": niche,
                           "country": country, "budget_usd": budget})
            label = {"listing": "Listing 生成", "image": "图片生成",
                     "advertising": "广告分析"}[intent]
            reason = f"识别为{label}：产品={prod} @ {country}"
        else:
            niche = category or _fallback_niche(query)
            if not niche:
                return SupervisorPlan(intent=intent, routed_agents=[],
                                      reason="缺少利基/产品参数，需追问。",
                                      params={"country": country})
            if intent == "competitor":
                params["niche_keyword"] = niche
                reason = f"识别为竞品分析：利基={niche} @ {country}"
            elif intent == "voc":
                params["product_name"] = niche
                reason = f"识别为 VOC 分析：产品={niche} @ {country}"
            else:  # product
                params.update({"niche_keyword": niche, "budget_usd": budget})
                reason = f"识别为产品机会判断：利基={niche} @ {country}/预算${budget}"
        return SupervisorPlan(intent=intent, routed_agents=[intent], reason=reason, params=params)

    def run(self, query: str) -> AgentRunResult:
        plan = self.plan(query)
        if plan.intent == "unknown":
            return AgentRunResult(intent="unknown", routed_agents=[],
                                  plan_reason=plan.reason, params=plan.params,
                                  clarification="请告诉我你想做：蓝海市场挖掘 / 竞品分析 / 用户评论(VOC)分析 / 产品机会判断 / Listing 生成 / 图片生成 / 商品视觉 / 广告分析 / 生命周期看板？")
        if plan.intent == "lifecycle":
            return AgentRunResult(intent="lifecycle", routed_agents=[],
                                  plan_reason=plan.reason, params=plan.params)
        if plan.intent == "visual":
            return AgentRunResult(intent="visual", routed_agents=[],
                                  plan_reason=plan.reason, params=plan.params)
        if not plan.routed_agents:
            return AgentRunResult(intent=plan.intent, routed_agents=[],
                                  plan_reason=plan.reason, params=plan.params,
                                  clarification="缺少必要参数（类目、产品名或利基），请补充后重试。")

        try:
            tool = next(t for t in SUPERVISOR_TOOLS if t["name"] == f"call_{plan.intent}_agent")
            out = tool["handler"](plan.params)
        except Exception as e:  # 专家 Agent 执行失败（如缺凭证）不击穿 Supervisor
            return AgentRunResult(intent=plan.intent, routed_agents=plan.routed_agents,
                                  plan_reason=plan.reason, params=plan.params,
                                  clarification=f"专家 Agent 执行失败：{e}")

        result = AgentRunResult(intent=plan.intent, routed_agents=plan.routed_agents,
                                plan_reason=plan.reason, params=plan.params)
        setattr(result, plan.intent, out)
        return result
