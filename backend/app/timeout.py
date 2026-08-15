"""请求级超时与阻塞调用封装（P1-4 同步阻塞治理）。

背景：Agent 端点（Supervisor / Market Research / Listing / 视觉 / 广告 …）是同步
``def``，内部串行调用 Agnes（单次 60s × 3 重试 ≈ 180s）与 Bright Data，跑在
uvicorn threadpool 上——调用方无法被框架超时取消，长调用会占死 worker、客户端悬挂。

解法：把阻塞调用放进独立线程（``asyncio.to_thread``）并整体 ````asyncio.wait_for````
设超时。端点改为 ``async def`` 后，外部 IO 期间**事件循环不被阻塞**，并发请求
仍可得到响应；超时时及时返回 504（降级），后台线程由有界执行器回收。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger("aigos.timeout")

T = TypeVar("T")


class RequestTimeoutError(Exception):
    """请求在限定时间内未完成，由 :func:`run_blocking_with_timeout` 抛出。

    由 ``app.errors`` 的专用处理器映射为 HTTP 504 + 统一 JSON 错误体。
    """


async def run_blocking_with_timeout(
    func: Callable[..., T],
    *args: Any,
    timeout: float | None = None,
    **kwargs: Any,
) -> T:
    """在线程中运行阻塞函数（外部 IO），并以 ``timeout`` 秒设整体超时。

    - ``func`` 可为普通函数或可调用（如 ``ListingAgent().run``）。
    - 超时抛出 :class:`RequestTimeoutError`（不抛出裸 ``asyncio.TimeoutError``，
      避免被通用 500 处理器误判）。
    - ``timeout`` 缺省取 ``app.config.AGENT_TIMEOUT_SECONDS``。
    """
    if timeout is None:
        from app.config import AGENT_TIMEOUT_SECONDS

        timeout = float(AGENT_TIMEOUT_SECONDS)
    name = getattr(func, "__name__", repr(func))
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(func, *args, **kwargs), timeout=timeout
        )
    except asyncio.TimeoutError as exc:
        logger.warning("请求超时（>%.0fs）：%s", timeout, name)
        raise RequestTimeoutError(
            f"请求处理超时（上限 {int(timeout)}s），请稍后重试或拆分任务"
        ) from exc
