"""轻量级内存速率限制器（P0-3）。

设计取舍（为什么不用 slowapi）：
- 项目 Bright Data 客户端已采用「零依赖标准库实现」风格；这里同样用标准库实现一个
  固定窗口限流器，**不引入 slowapi/limits 新依赖**，也避免为 8 个路由文件逐个补
  ``request: Request`` 参数（slowapi 的 ``@limiter.limit`` 装饰器要求端点签名必须含
  ``request``，否则运行时直接报错）。
- 限流键：优先用已鉴权的 API Key；未启用鉴权时回退到客户端 IP
  （``request.client.host`` / ``X-Forwarded-For``）。即「同一 key 或同一 IP」共享配额。
- 全局默认 20 req/min；重操作（agent run / market_research，天然烧 Bright Data / AGNES
  额度）单独 5 req/min。
- 多 worker / 多实例部署需共享状态时，把 ``Window.bucket`` 换成 Redis（见 P0-4 的
  docker-compose 注释）——当前为单进程内存实现。

返回：超阈值抛 ``HTTPException(429)``，带 ``Retry-After`` 与 ``X-RateLimit-*`` 响应头。
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from fastapi import Depends, HTTPException, Request, status

from app.config_store import get as config_get
from app.security import get_current_key

# 配额（可由环境变量覆盖，便于运维调参；改完需重启生效）
DEFAULT_TIMES = int(config_get("RATELIMIT_DEFAULT_TIMES", "") or 20)
DEFAULT_SECONDS = int(config_get("RATELIMIT_DEFAULT_SECONDS", "") or 60)
HEAVY_TIMES = int(config_get("RATELIMIT_HEAVY_TIMES", "") or 5)
HEAVY_SECONDS = int(config_get("RATELIMIT_HEAVY_SECONDS", "") or 60)


class Window:
    """固定窗口计数器：记录窗口期内的命中时间戳，超阈值即拒绝。"""

    __slots__ = ("times", "seconds", "bucket")

    def __init__(self, times: int, seconds: int):
        self.times = times
        self.seconds = seconds
        self.bucket: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, ident: str) -> Tuple[bool, int]:
        """返回 ``(是否放行, 建议退避秒数)``。"""
        now = time.monotonic()
        dq = self.bucket[ident]
        cutoff = now - self.seconds
        while dq and dq[0] <= cutoff:
            dq.popleft()
        if len(dq) >= self.times:
            # 最早一次命中还可存活的秒数即建议退避
            retry = int(dq[0] + self.seconds - now) + 1
            return False, max(retry, 1)
        dq.append(now)
        return True, 0

    def reset(self) -> None:
        """测试用：清空所有计数。"""
        self.bucket.clear()


# 限流器注册表（单例存活于进程内）
_STORES: Dict[str, Window] = {}


def _get_window(name: str, times: int, seconds: int) -> Window:
    w = _STORES.get(name)
    if w is None:
        w = Window(times, seconds)
        _STORES[name] = w
    return w


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client.host if request.client else "unknown") or "unknown"


def _identity(request: Request, api_key: str) -> str:
    # 已鉴权：以 key 维度限流；否则以 IP 维度。
    if api_key:
        return f"key:{api_key}"
    return f"ip:{_client_ip(request)}"


def _too_many(ident: str, retry: int, limit: int, window: int) -> HTTPException:
    # 不把 ident 细节泄露给客户端，只给配额与退避建议。
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"请求过于频繁，请在 {retry} 秒后重试（限制 {limit} 次 / {window}s）。",
        headers={
            "Retry-After": str(retry),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Window": str(window),
        },
    )


def rate_limit_default(request: Request, api_key: str = Depends(get_current_key)) -> None:
    """依赖：全局默认配额（20/min）。挂到所有受保护路由。"""
    ident = _identity(request, api_key)
    w = _get_window("default", DEFAULT_TIMES, DEFAULT_SECONDS)
    allowed, retry = w.check(ident)
    if not allowed:
        raise _too_many(ident, retry, DEFAULT_TIMES, DEFAULT_SECONDS)


def rate_limit_heavy(request: Request, api_key: str = Depends(get_current_key)) -> None:
    """依赖：重操作配额（5/min）。挂到 agent run / market_research 等烧额度端点。"""
    ident = _identity(request, api_key)
    w = _get_window("heavy", HEAVY_TIMES, HEAVY_SECONDS)
    allowed, retry = w.check(ident)
    if not allowed:
        raise _too_many(ident, retry, HEAVY_TIMES, HEAVY_SECONDS)
