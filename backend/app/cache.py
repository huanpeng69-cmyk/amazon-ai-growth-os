"""轻量 TTL 缓存（P2-1，零新依赖，仅标准库）。

用于缓存昂贵且可复用的外部结果（如市场调研：Bright Data 取数 + LLM 分析）。
- 线程安全（单进程内多 worker 共享同一进程内存；多实例需换 Redis，见下）；
- 按 TTL 过期、按容量 FIFO 淘汰；
- 不缓存异常，仅缓存成功结果。

多实例 / 多 worker 共享：当前为进程内缓存，gunicorn 多 worker 各自独立。
若要跨 worker 共享，把 `_store` 换成 Redis（沿用 requirements 中已锁定的 redis）。
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional, Tuple

from app.config import RESEARCH_CACHE_MAXSIZE, RESEARCH_CACHE_TTL_SECONDS


class TTLCache:
    """极简线程安全 TTL 缓存。"""

    def __init__(self, maxsize: int = 256, default_ttl: int = 600):
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self._store: dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            value, exp = item
            if exp <= time.monotonic():
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = self._default_ttl if ttl is None else ttl
        if ttl <= 0:
            return  # TTL<=0 视为关闭缓存
        with self._lock:
            if len(self._store) >= self._maxsize:
                # FIFO 淘汰最旧一项（dict 保插入顺序）
                try:
                    self._store.pop(next(iter(self._store)))
                except StopIteration:
                    pass
            self._store[key] = (value, time.monotonic() + ttl)

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[int] = None) -> Tuple[Any, bool]:
        """命中返回 (value, True)；未命中则 factory() 并写入，返回 (value, False)。"""
        cached = self.get(key)
        if cached is not None:
            return cached, True
        value = factory()
        self.set(key, value, ttl)
        return value, False


# 市场调研结果缓存（进程内共享实例）
research_cache = TTLCache(maxsize=RESEARCH_CACHE_MAXSIZE, default_ttl=RESEARCH_CACHE_TTL_SECONDS)
