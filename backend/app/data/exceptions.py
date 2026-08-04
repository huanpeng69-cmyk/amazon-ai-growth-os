"""数据层异常。

统一继承 ConnectorError，并携带 HTTP 状态码，便于 router 层直接映射。
"""
from __future__ import annotations


class ConnectorError(Exception):
    """数据层/连接器通用错误。"""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class ConnectorNotConfigured(ConnectorError):
    """连接器未配置真实凭证（Live 模式不可用）。返回 501。"""

    def __init__(self, message: str = ""):
        super().__init__(message or "Connector 未配置真实凭证，当前不可用（请配置 API Key 或切换到 fixture 模式）", 501)


class FixtureMissing(ConnectorError):
    """fixture 样本数据缺失。返回 404。"""

    def __init__(self, message: str = ""):
        super().__init__(message or "Connector 的 fixture 样本数据缺失", 404)


class DataNotFound(ConnectorError):
    """连接器返回但关键数据缺失/为空。返回 404。"""

    def __init__(self, message: str = ""):
        super().__init__(message or "未找到所需数据", 404)
