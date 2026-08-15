"""集中式结构化 JSON 日志配置（P1-2）。

- 用 ``logging.config.dictConfig`` 把根日志配置为**单行 JSON** 输出到 stdout，
  字段含 ``timestamp`` / ``level`` / ``logger`` / ``message`` / ``request_id`` /
  ``trace_id`` / 位置（module/func/line）/ 异常文本；
- 请求级 ``request_id`` 通过 ``contextvars`` 在请求处理流内注入（与 P1-1 的
  ``trace_id`` 同源，见 ``middleware.TraceIDMiddleware``）；
- 异常日志（见 ``errors.py``）额外以 ``extra={"trace_id": ...}`` 传入，即使跨异常
  边界 contextvars 断裂也能带 ``trace_id``。

不引入 python-json-logger 等新依赖，沿用项目「标准库实现」风格。
"""
from __future__ import annotations

import contextvars
import json
import logging
import logging.config
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict

# 请求级 ID：由 TraceIDMiddleware 在请求开始时 set，正常处理流内（含被丢到线程池的
# sync 端点，因为 anyio 用 copy_context 传播）都可读取。异常 handler 跨边界不可靠，
# 故 errors.py 另以 extra 显式传入（见 JsonFormatter 的 fallback）。
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("aigos_request_id", default="")


class JsonFormatter(logging.Formatter):
    """把 LogRecord 渲染成单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        request_id = request_id_var.get() or getattr(record, "request_id", "") or "-"
        trace_id = getattr(record, "trace_id", "") or request_id

        # 异常文本：仅当显式传入 exc_info（异常日志）时附带，避免正常日志出现堆栈
        exc_text = ""
        if record.exc_info:
            exc_text = "".join(traceback.format_exception(*record.exc_info)).strip()

        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage().replace("\n", " ⏎ "),
            "request_id": request_id,
            "trace_id": trace_id,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        if exc_text:
            payload["error"] = exc_text

        return json.dumps(payload, ensure_ascii=False, default=str)


_CONFIGURED = False


def configure_logging() -> None:
    """配置根日志为 JSON 输出（幂等，重复调用不会叠加 handler）。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,  # 保留 uvicorn 等第三方 logger 的配置
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "json_console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                }
            },
            "root": {"level": level, "handlers": ["json_console"]},
        }
    )
    # 保留对 handler 的引用（dictConfig 内部已装配，这里仅确保级别正确）
    handler.setLevel(level)
    _CONFIGURED = True


def get_request_id() -> str:
    """当前请求 ID（供非日志场景读取，如调试）。"""
    return request_id_var.get()
