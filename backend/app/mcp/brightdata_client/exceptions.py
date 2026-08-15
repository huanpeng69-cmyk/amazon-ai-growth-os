"""Bright Data MCP 客户端的异常体系。

所有异常都继承自 BrightDataError，便于调用方统一捕获 / 降级。
"""
from __future__ import annotations


class BrightDataError(Exception):
    """Bright Data MCP 客户端所有错误的基类。"""

    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BrightDataAuthError(BrightDataError):
    """鉴权失败（API Key 缺失 / 无效 / 401-403）。"""

    def __init__(self, message: str = "Bright Data 鉴权失败：请检查 BRIGHTDATA_API_KEY"):
        super().__init__(message, status_code=401)


class BrightDataTransportError(BrightDataError):
    """传输层错误（网络 / HTTP / 超时 / 非重试型 4xx）。"""

    def __init__(self, message: str):
        super().__init__(message, status_code=502)


class BrightDataServerError(BrightDataTransportError):
    """Bright Data 服务端 5xx 错误（**可重试**，客户端应退避后重试）。"""

    def __init__(self, message: str):
        super().__init__(message)


class BrightDataRateLimitError(BrightDataError):
    """被 Bright Data 限流（HTTP 429）。

    携带 ``retry_after``（秒），客户端应至少退避该时长后再试。
    """

    def __init__(self, retry_after: int | None, message: str = ""):
        self.retry_after = retry_after
        suffix = f"，建议退避 {retry_after}s" if retry_after else ""
        super().__init__(f"Bright Data 限流（429）{suffix}：{message}".strip(), status_code=429)


class BrightDataProtocolError(BrightDataError):
    """JSON-RPC 协议层错误（非 2.0 / 缺字段 / 解析失败）。"""

    def __init__(self, message: str):
        super().__init__(message, status_code=502)


class BrightDataToolError(BrightDataError):
    """Bright Data 返回的 tools/call 业务错误（isError=true 或 result 异常）。"""

    def __init__(self, message: str, *, tool: str | None = None):
        self.tool = tool
        suffix = f"（tool={tool}）" if tool else ""
        super().__init__(f"Bright Data 工具调用失败{suffix}：{message}", status_code=502)


class BrightDataToolNotFound(BrightDataError):
    """在 tools/list 中找不到匹配的工具名。"""

    def __init__(self, candidates: list[str], available: list[str] | None = None):
        self.candidates = candidates
        self.available = available or []
        avail = f"；服务端可用工具：{', '.join(self.available)}" if self.available else ""
        super().__init__(
            f"未找到匹配的工具（候选：{', '.join(candidates)}）{avail}",
            status_code=404,
        )
