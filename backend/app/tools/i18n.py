"""轻量中文→英文词条表（确定性兜底翻译）。

用途：当未配置 Agnes 等真实文本 LLM 时，让确定性文案引擎也能把常见的跨境选品
中文词（宠物 / 家居 / 厨房等）转成英文，从而在没有 API Key 的情况下产出「全英文」
Listing / 广告文案。通用翻译仍走 Agnes（见 app/llm/agnes.py）。

仅覆盖高频词；未命中词保持原样（best-effort），并可由上层提示用户配置 AGNES_API_KEY
以获得完整中文→英文翻译。
"""
from __future__ import annotations

import re

_GLOSSARY = {
    # 宠物 / 动物
    "超静音": "Ultra-Quiet", "静音": "Quiet", "噪音": "Noise",
    "猫咪": "Cat", "猫": "Cat", "小狗": "Puppy", "狗": "Dog", "宠物": "Pet", "鱼": "Fish", "鸟": "Bird",
    "饮水机": "Water Fountain", "水泵": "Pump", "水箱": "Water Tank", "喂食器": "Feeder",
    "猫砂盆": "Litter Box", "项圈": "Collar", "牵引绳": "Leash", "狗窝": "Dog Bed", "猫窝": "Cat Bed",
    "玩具": "Toy", "梳": "Brush", "碗": "Bowl", "垫": "Mat", "笼": "Crate", "窝": "Bed",
    # 材质 / 属性
    "可拆洗": "Detachable", "拆洗": "Detachable", "易清洗": "Easy-Clean", "清洗": "Clean",
    "食品级": "Food-Grade", "材质": "Material", "无毒": "Non-Toxic", "环保": "Eco-Friendly",
    "防水": "Waterproof", "漏水": "Leakproof", "大容量": "Large Capacity", "容量": "Capacity",
    "续航": "Long Battery", "智能": "Smart", "无线": "Wireless", "便携": "Portable",
    "折叠": "Foldable", "耐用": "Durable", "防滑": "Non-Slip", "加厚": "Thickened",
    "恒温": "Constant Temperature", "自动": "Automatic", "电动": "Electric",
    "不锈钢": "Stainless Steel", "陶瓷": "Ceramic", "硅胶": "Silicone", "塑料": "Plastic",
    "木质": "Wooden", "棉": "Cotton", "麻": "Linen",
    # 场景
    "家用": "Home", "户外": "Outdoor", "旅行": "Travel", "厨房": "Kitchen", "浴室": "Bathroom",
    "卧室": "Bedroom", "办公室": "Office", "车载": "Car", "花园": "Garden", "婴儿": "Baby",
    # 通用
    "高清": "HD", "充电": "Rechargeable", "升级": "Upgraded", "饮水": "Hydration",
    "加湿": "Humidifying", "加热": "Heating", "制冷": "Cooling", "净化": "Purifying",
    "新款": "New", "正品": "Genuine", "豪华": "Luxury", "专业": "Professional",
}

_KEYS = sorted(_GLOSSARY.keys(), key=len, reverse=True)
_PATTERN = re.compile("|".join(re.escape(k) for k in _KEYS))


def cn_to_en(text: str) -> str:
    """把字符串中的已知中文词替换为英文；未命中词保持原样。"""
    if not text:
        return text
    out = _PATTERN.sub(lambda m: " " + _GLOSSARY[m.group(0)] + " ", text)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def translate_list(items: list[str]) -> list[str]:
    return [cn_to_en(x) for x in items]
