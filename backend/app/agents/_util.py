"""Agent 共用工具：把"真实数据 → 大模型合成"这条链路标准化。

设计原则（与 VOC Agent 一致）：
- 任何面向用户的"分析 / 痛点 / 建议 / 总结"文案都必须由大模型基于*真实数据*生成，
  绝不能来自硬编码模板、固定常量或编造的数字；
- 大模型不可用时，降级为"诚实告知"，绝不编造内容。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from app.llm.agnes import AgnesError, agnes

log = logging.getLogger("agents.util")


def extract_json(text: str) -> dict:
    """从 LLM 回复中稳健解析 JSON（兼容 ```json 代码块与前后多余文本）。"""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except json.JSONDecodeError:
                pass
        raise AgnesError(f"LLM 返回无法解析为 JSON：{text[:300]}")


def synthesize(system: str, user: str, *, temperature: float = 0.4,
               max_tokens: int = 1400, retries: int = 3) -> dict:
    """调用 Agnes 大模型并经稳健解析返回 JSON。

    失败时抛出 AgnesError，由调用方决定降级策略（诚实告知，不编造）。
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_err: Optional[Exception] = None
    for _ in range(retries):
        try:
            text = agnes.chat(messages, temperature=temperature, max_tokens=max_tokens)
        except Exception as e:  # 任何异常（含网络瞬时断开）均视为可重试/可降级
            last_err = e
            continue
        if not text or not text.strip():
            last_err = AgnesError("LLM 返回空响应")
            continue
        try:
            return extract_json(text)
        except AgnesError as e:
            last_err = e
            continue
    raise AgnesError(f"大模型合成失败：{last_err}")


def llm_available() -> bool:
    return agnes.enabled()
