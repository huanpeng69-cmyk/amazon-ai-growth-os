"""Agnes 客户端单测：聚焦「任何网络/解析失败都统一包装为 AgnesError」这一关键契约。

背景：此前 agnes.chat 在服务器瞬时断开时会抛出裸的 http.client.RemoteDisconnected，
穿透了所有 `except AgnesError` 降级逻辑，导致竞品/市场等端点间歇 500。
修复后 _post() 必须：
- 对 4xx（非 429、<500）立即抛 AgnesError（不重试，重试无意义）；
- 对 429/5xx/URLError/RemoteDisconnected/JSON 解析失败 重试 3 次；
- 重试耗尽后包装为 AgnesError，绝不向调用方泄漏裸网络异常。
"""
from __future__ import annotations

import http.client
import json
from unittest import mock

import pytest
import urllib.error

from app.llm.agnes import AgnesClient, AgnesError


def _fake_resp(payload: dict) -> mock.MagicMock:
    fake = mock.MagicMock()
    fake.read.return_value = json.dumps(payload).encode("utf-8")
    # MagicMock 默认的 __enter__ 会返回一个新的 Mock，导致 resp.read() 失效；
    # 显式让它返回自身，才能模拟 `with urlopen(...) as resp` 的真实行为。
    fake.__enter__.return_value = fake
    return fake


def test_post_success_returns_parsed_json():
    with mock.patch("urllib.request.urlopen", return_value=_fake_resp({"ok": 1})) as m:
        out = AgnesClient()._post("http://x", {"a": 1})
    assert out == {"ok": 1}
    assert m.call_count == 1


def test_post_4xx_raises_agneserror_without_retry():
    err = urllib.error.HTTPError("http://x", 400, "Bad", {}, None)
    with mock.patch("urllib.request.urlopen", side_effect=err) as m:
        with pytest.raises(AgnesError):
            AgnesClient()._post("http://x", {})
    # 4xx 客户端错误不应重试
    assert m.call_count == 1


def test_post_429_retries_then_agneserror():
    err = urllib.error.HTTPError("http://x", 429, "Too Many", {}, None)
    with mock.patch("urllib.request.urlopen", side_effect=err) as m:
        with pytest.raises(AgnesError):
            AgnesClient()._post("http://x", {})
    assert m.call_count == 3


def test_post_5xx_retries_then_agneserror():
    err = urllib.error.HTTPError("http://x", 503, "Down", {}, None)
    with mock.patch("urllib.request.urlopen", side_effect=err) as m:
        with pytest.raises(AgnesError):
            AgnesClient()._post("http://x", {})
    assert m.call_count == 3


def test_post_remote_disconnected_wrapped_as_agneserror():
    """回归测试：裸 RemoteDisconnected 必须被包装为 AgnesError，而非穿透导致 500。"""
    with mock.patch(
        "urllib.request.urlopen",
        side_effect=http.client.RemoteDisconnected("Connection closed"),
    ) as m:
        with pytest.raises(AgnesError):
            AgnesClient()._post("http://x", {})
    assert m.call_count == 3


def test_post_urlerror_retries_then_agneserror():
    err = urllib.error.URLError("dns failure")
    with mock.patch("urllib.request.urlopen", side_effect=err) as m:
        with pytest.raises(AgnesError):
            AgnesClient()._post("http://x", {})
    assert m.call_count == 3


def test_chat_malformed_response_raises_agneserror():
    """响应格式异常（缺 choices）必须抛 AgnesError，而非 KeyError 穿透。"""
    with mock.patch("urllib.request.urlopen", return_value=_fake_resp({"unexpected": 1})), \
         mock.patch("app.llm.agnes._cfg", lambda k, d="": "test-key" if k == "AGNES_API_KEY" else d):
        with pytest.raises(AgnesError):
            AgnesClient().chat([{"role": "user", "content": "x"}])


def test_chat_disabled_without_key_raises_agneserror():
    """未配置 API Key 时 chat 应优雅抛 AgnesError，而不是发起请求。"""
    with mock.patch("app.llm.agnes._cfg", lambda k, d="": ""):
        with pytest.raises(AgnesError):
            AgnesClient().chat([{"role": "user", "content": "x"}])
