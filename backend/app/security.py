"""API 鉴权依赖（P0-2）。

设计（与既有 SETTINGS_API_TOKEN 一致——「配置即启用，未配置则开放」）：
- 仅在环境变量 / 运行时配置 ``API_AUTH_TOKEN`` 非空时才强制鉴权，避免破坏本地单用户演示；
- 支持三种携带方式：``Authorization: Bearer <key>``、``X-API-Key: <key>``、``?api_key=<key>``；
- 校验失败统一返回 401；密钥只存于环境变量 / config_store，绝不进代码。
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from app.config_store import get as _cfg


def requires_api_key() -> bool:
    """是否已启用 API 鉴权（配置了 API_AUTH_TOKEN 才启用）。"""
    return bool(_cfg("API_AUTH_TOKEN", ""))


def get_current_key(request: Request) -> str:
    """FastAPI 依赖：校验请求是否携带有效 API Key。

    未启用（无 API_AUTH_TOKEN）时直接放行并返回空串，保持向后兼容。
    """
    if not requires_api_key():
        return ""
    auth = request.headers.get("authorization", "")
    bearer = auth.removeprefix("Bearer ").strip() if auth.lower().startswith("bearer ") else ""
    provided = (
        bearer
        or request.headers.get("x-api-key", "").strip()
        or (request.query_params.get("api_key") or "").strip()
    )
    expected = _cfg("API_AUTH_TOKEN", "")
    if provided and provided == expected:
        return provided
    raise HTTPException(
        status_code=401,
        detail="API 需要鉴权：请提供有效的 API Key（Authorization: Bearer 或 X-API-Key）",
    )
