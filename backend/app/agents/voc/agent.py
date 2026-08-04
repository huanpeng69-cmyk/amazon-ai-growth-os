"""VOC Agent —— 执行器。"""
from __future__ import annotations

from app.agents.voc.schemas import PainPointOut, VOCInput, VOCOutput
from app.agents.voc.tools import VOC_TOOLS

_FIX_MAP = {
    "易残留异味/染色": "采用食品级不串味材质 + 可拆洗结构",
    "塑料遇热释放有害物质": "升级为 BPA-Free / 食品级硅胶材质",
    "密封不严导致串味": "加强密封圈与卡扣设计",
    "占用橱柜空间大": "做可叠放 / 折叠收纳结构",
    "清洗困难": "一体化无死角、可 dishwasher 设计",
    "手柄易松动": "加固铆接 / 一体成型手柄",
    "阻力带易断裂": "加厚 latex 层 + 纺织包覆",
    "占空间大不便收纳": "附壁挂/折叠收纳方案",
    "握把打滑": "增加防滑纹理 / 吸汗材质",
    "噪音扰民": "静音电机 + 减震脚垫",
    "做工粗糙硌皮肤": "圆角抛光 + 亲肤包胶",
    "水易脏/滋生细菌": "流动水循环 + 易拆洗水路",
    "宠物拒绝使用": "低噪 + 自然水流引导",
    "噪音惊吓宠物": "超静音水泵",
    "材质不安全": "全系列食品级 / 母婴级认证",
    "续航不足": "大容量电池 + 快充",
    "重量偏重": "轻量化材质（碳纤维/铝）",
    "防水不达标": "IPX6 以上防水",
}


def _fix(pain: str) -> str:
    return _FIX_MAP.get(pain, f"针对「{pain}」做针对性的产品/体验升级")


class VOCAgent:
    name = "voc"
    description = "用户声音分析：产品/利基 → 痛点排序 + 改进建议 + 优势提炼"

    def run(self, inp: VOCInput) -> VOCOutput:
        fetch = next(t for t in VOC_TOOLS if t["name"] == "fetch_reviews")["handler"]
        data = fetch(inp.product_name, inp.country)

        pts = sorted(data["pain_points"], key=lambda p: (p["base_severity"], p["evidence"]), reverse=True)
        pain_points = [
            PainPointOut(pain=p["pain"], severity=p["base_severity"],
                         evidence=p["evidence"], suggested_fix=_fix(p["pain"]))
            for p in pts
        ]
        top = pain_points[0] if pain_points else None
        _gy = data.get("growth_yoy")
        gy_str = f"{_gy * 100:.0f}%" if _gy is not None else "N/A"
        strengths = [f"类目年增速 {gy_str}", "搜索需求稳定", "头部尚未完全满足痛点"]
        summary = (f"「{data['product_name']}」评论中共识别 {len(pain_points)} 个主要痛点，"
                   f"最突出为「{top.pain}」（严重度 {top.severity}、证据 {top.evidence} 条）。"
                   if top else f"「{data['product_name']}」暂无明显痛点信号。")
        return VOCOutput(
            product_name=data["product_name"], country=inp.country,
            pain_points=pain_points, strengths=strengths, summary=summary)
