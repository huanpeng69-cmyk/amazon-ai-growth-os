"""P0-3 Bright Data 客户端韧性测试。

验证点（client.py 的 _post / _rpc 重试链路）：
- 5xx / 连接错误：指数退避重试，最终成功则不报错；
- 429（带 Retry-After）：重试并尊重服务端退避建议；
- 4xx（400 等）/ 401：不可重试，立即抛出；
- 并发信号量：max_concurrent_calls 限制同时发出的调用数；
- _parse_retry_after：秒数 / HTTP-date / 非法值兜底；
- MockTransport 路径回归：重构后 call_tool 仍正常。
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from app.mcp.brightdata_client.client import (
    BrightDataMCPClient,
    MockTransport,
    StreamableHttpTransport,
    _parse_retry_after,
)
from app.mcp.brightdata_client.exceptions import (
    BrightDataAuthError,
    BrightDataRateLimitError,
    BrightDataServerError,
    BrightDataTransportError,
)


def _raise(exc):
    def _f():
        raise exc

    return _f


def _ok(value):
    def _f():
        return value

    return _f


class ScriptedTransport(StreamableHttpTransport):
    """用预置行为脚本覆盖 _send_once，便于离线验证重试/退避。"""

    def __init__(self, behaviors, **kw):
        kw.setdefault("max_retries", 3)
        kw.setdefault("backoff_base", 0)
        kw.setdefault("backoff_max", 0)
        kw.setdefault("max_concurrent_calls", 4)
        super().__init__("https://example.com/mcp", "fake-key", **kw)
        self._behaviors = list(behaviors)
        self.send_calls = 0

    def _send_once(self, payload):
        self.send_calls += 1
        fn = self._behaviors.pop(0)
        return fn()


# ───────────────────────── 重试 / 退避 ─────────────────────────
def test_retries_then_succeeds_on_5xx():
    t = ScriptedTransport(
        [_raise(BrightDataServerError("503")), _raise(BrightDataServerError("503")), _ok({"ok": 1})]
    )
    assert t.request({}) == {"ok": 1}
    assert t.send_calls == 3  # 2 次失败 + 1 次成功


def test_retries_429_respecting_retry_after():
    script = [_raise(BrightDataRateLimitError(2, "slow down"))] * 4
    t = ScriptedTransport(script, backoff_max=0)
    with pytest.raises(BrightDataRateLimitError) as ei:
        t.request({})
    assert ei.value.retry_after == 2
    assert t.send_calls == 4  # max_retries=3 → 共 4 次尝试


def test_4xx_not_retried():
    t = ScriptedTransport([_raise(BrightDataTransportError("HTTP 400"))])
    with pytest.raises(BrightDataTransportError):
        t.request({})
    assert t.send_calls == 1  # 立即抛出，无重试


def test_auth_error_not_retried():
    t = ScriptedTransport([_raise(BrightDataAuthError())])
    with pytest.raises(BrightDataAuthError):
        t.request({})
    assert t.send_calls == 1


def test_backoff_respects_retry_after_and_cap():
    t = StreamableHttpTransport("https://x/mcp", "k", backoff_base=0.5, backoff_max=8.0)
    assert t._backoff(0, 2) == 2.0          # 服务端建议优先
    assert t._backoff(0, None) == 0.5        # 指数退避基线
    assert t._backoff(3, None) == 4.0        # 0.5 * 2^3 = 4, 封顶 8
    assert t._backoff(0, 100) == 8.0         # Retry-After 超上限被封顶


# ───────────────────────── 并发信号量 ─────────────────────────
def test_concurrency_semaphore_limits_parallel_calls():
    cap = {"cur": 0, "max": 0}
    lk = threading.Lock()

    class Bounded(StreamableHttpTransport):
        def _send_once(self, payload):
            with lk:
                cap["cur"] += 1
                cap["max"] = max(cap["max"], cap["cur"])
            time.sleep(0.05)
            with lk:
                cap["cur"] -= 1
            return {"ok": True}

    t = Bounded("https://x/mcp", "k", max_concurrent_calls=2)
    threads = [threading.Thread(target=t.request, args=({},)) for _ in range(6)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert cap["max"] <= 2


# ───────────────────────── 解析辅助 ─────────────────────────
def test_parse_retry_after():
    import email.utils

    assert _parse_retry_after("5") == 5
    assert _parse_retry_after("  3  ") == 3
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("") is None
    assert _parse_retry_after("not-a-number") is None
    dt = email.utils.formatdate(time.time() + 3, usegmt=True)
    val = _parse_retry_after(dt)
    assert val in (2, 3, 4)  # HTTP-date 近似秒数


# ───────────────────────── 回归：Mock 路径 ─────────────────────────
def test_mock_transport_still_works_after_refactor():
    mt = MockTransport().on(
        "tools/call", lambda p: {"content": [{"type": "text", "text": json.dumps({"k": 1})}]}
    )
    client = BrightDataMCPClient(transport=mt, auto_init=False)
    assert client.call_tool("whatever", {}) == {"k": 1}


def test_client_constructible_without_network():
    # auto_init=False 不应触发任何网络；仅验证构造与配置读取不崩。
    client = BrightDataMCPClient(auto_init=False)
    assert client.max_retries >= 0
