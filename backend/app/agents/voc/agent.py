"""VOC Agent —— 执行器。

改进建议不再使用硬编码的产品专属映射（此前围绕水泵产品建），
改为「通用映射 + 上下文感知模板」双轨制：
- 少数真正跨品类的痛点（说明书、售后、包装等）保留固定建议；
- 大多数常见痛点（做工、尺寸、功能故障等）根据实际分析的产品名动态生成；
- 完全未命中的痛点给出通用的品类化建议。
"""
from __future__ import annotations

from app.agents.voc.schemas import PainPointOut, VOCInput, VOCOutput
from app.agents.voc.tools import VOC_TOOLS

# ── 真正跨品类的通用映射（不依赖具体产品形态）─
_UNIVERSAL_FIXES = {
    "说明差/poor instructions": "图文说明书 + 视频引导",
    "货不对板/misleading": "如实标注规格 + 强化质检",
    "售后/customer service": "延长质保 + 快速响应通道",
    "缺陷/defective": "出厂全检 + 换新保障",
    "偏贵/too expensive": "推出性价比款 / 组合装优惠",
    "难用/hard to use": "简化操作流程 + 清晰指引",
}

# ── 上下文感知模板：pain_key → 建议模板（含 {product} 占位符）─
# 这些模板适用于绝大多数品类，会自动填入当前分析的产品名。
_CONTEXTUAL_TEMPLATES = {
    # 质量类
    "做工差/cheap": "提升{product}的材质与工艺标准，强化出厂品控",
    "质量差/poor quality": "加固{product}核心结构，提升整体耐用性",
    # 功能失效类
    "停止工作/stopped working": "优化{product}的关键部件设计，延长使用寿命",
    "不工作/doesn't work": "排查{product}故障高发点，加强可靠性测试",
    # 尺寸类
    "太小/too small": "推出大容量/加大版{product}，覆盖更多场景",
    "太大/too big": "提供紧凑/便携版{product}，改善收纳体验",
    # 感官类
    "噪音/noisy": "优化{product}的运行静音表现",
    "异味/bad smell": "采用更安全环保的{product}材质方案",
    "不适/uncomfortable": "优化{product}的人体工学与触感设计",
    # 耐用类
    "生锈/rusting": "升级{product}为防锈/耐腐蚀材质",
    "发霉/mold": "改善{product}的防潮抗菌设计",
    # 性能类
    "慢/slow": "优化{product}的响应速度与处理效率",
    "过热/overheating": "加强{product}散热设计与温控保护",
    "续航不足/short battery": "升级{product}电池容量与快充方案",
    "续航短/short battery": "升级{product}电池容量与快充方案",
    # 密封/清洁类
    "漏水/leaking": "加强{product}的密封结构与接口工艺",
    "滴水/dripping": "优化{product}防滴漏设计",
    "难清洗/hard to clean": "简化{product}的清洁维护设计",
    # 安全类
    "防水不达标": "将{product}防水等级提升至 IPX6 以上",
    "重量偏重": "采用轻量化材料重新设计{product}",
    # 其他
    "水易脏/滋生细菌": "优化{product}易拆洗/抗菌设计",
    "水有异味/bad taste": "升级{product}接触面材质与滤芯",
    "滤芯/filter issue": "升级{product}过滤系统并增加更换提醒",
    "水泵问题/pump issue": "优化{product}核心驱动部件可靠性",
    "塑料遇热释放有害物质": "将{product}材质升级为 BPA-Free / 食品级",
    "材质不安全": "全面采用安全认证材质生产{product}",
    "密封不严导致串味": "加强{product}密封圈与卡扣设计",
    "占用橱柜空间大": "为{product}设计可叠放/折叠收纳方案",
    "清洗困难": "为{product}做一体化无死角易清洗设计",
    "手柄易松动": "加固{product}握持部位连接结构",
    "阻力带易断裂": "加厚{product}受力部位材质",
    "占空间大不便收纳": "为{product}附壁挂/折叠收纳配件",
    "握把打滑": "在{product}握持区增加防滑纹理",
    "噪音扰民": "降低{product}运行噪音 + 加减震",
    "做工粗糙硌皮肤": "对{product}做圆角抛光 + 亲肤处理",
    "宠物拒绝使用": "降低{product}运行噪音 + 自然引导",
    "噪音惊吓宠物": "为{product}配备超静音模式",
}


def _fix(pain: str, product_name: str = "") -> str:
    """生成上下文感知的改进建议。

    优先级：
    1. 通用固定映射（不依赖品类）
    2. 上下文模板（自动填入产品名）
    3. 兜底：基于产品名的通用建议
    """
    # 1) 通用固定映射
    if pain in _UNIVERSAL_FIXES:
        return _UNIVERSAL_FIXES[pain]

    # 2) 上下文模板
    tmpl = _CONTEXTUAL_TEMPLATES.get(pain)
    if tmpl:
        label = product_name or "该产品"
        # 截取产品名前 15 字避免过长
        if len(label) > 15:
            label = label[:12] + "…"
        return tmpl.format(product=label)

    # 3) 兜底
    return f"针对「{pain}」对{product_name or '该产品'}做针对性升级"


class VOCAgent:
    name = "voc"
    description = "用户声音分析：产品/利基 → 痛点排序 + 改进建议 + 优势提炼"

    def run(self, inp: VOCInput) -> VOCOutput:
        fetch = next(t for t in VOC_TOOLS if t["name"] == "fetch_reviews")["handler"]
        data = fetch(inp.product_name, inp.country)

        pts = sorted(data["pain_points"], key=lambda p: (p["base_severity"], p["evidence"]), reverse=True)
        pain_points = [
            PainPointOut(pain=p["pain"], severity=p["base_severity"],
                         evidence=p["evidence"],
                         suggested_fix=_fix(p["pain"], data.get("product_name", inp.product_name)))
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
