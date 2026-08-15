"""_util 工具单测：extract_json 稳健解析 + synthesize 重试/降级契约。

这两处是「真实数据 → 大模型 → JSON 合成」链路的核心，必须保证：
- extract_json 能从容许 ```json 代码块、裸 JSON、前后带噪声文本中提取 JSON；
- 无法解析时抛 AgnesError（绝不返回半截垃圾）；
- synthesize 在 LLM 瞬时失败时重试，全部失败才抛 AgnesError（调用方据此诚实降级）。
"""
from __future__ import annotations

from unittest import mock

import pytest

from app.agents._util import extract_json, synthesize
from app.llm.agnes import AgnesError


def test_extract_json_code_block():
    assert extract_json("```json\n{\"x\": 1}\n```") == {"x": 1}


def test_extract_json_raw():
    assert extract_json('{"a": 2}') == {"a": 2}


def test_extract_json_surrounded_by_text():
    assert extract_json("前面废话 {\"k\": \"v\"} 后面废话") == {"k": "v"}


def test_extract_json_unparseable_raises():
    with pytest.raises(AgnesError):
        extract_json("这里没有任何 JSON 结构可言")


def test_synthesize_retries_then_succeeds():
    with mock.patch(
        "app.agents._util.agnes.chat",
        side_effect=[AgnesError("x"), AgnesError("y"), '{"ok": true}'],
    ) as m:
        out = synthesize("sys", "usr", retries=3)
    assert out == {"ok": True}
    assert m.call_count == 3


def test_synthesize_all_fail_raises_agneserror():
    with mock.patch("app.agents._util.agnes.chat", side_effect=AgnesError("boom")):
        with pytest.raises(AgnesError):
            synthesize("sys", "usr", retries=2)
