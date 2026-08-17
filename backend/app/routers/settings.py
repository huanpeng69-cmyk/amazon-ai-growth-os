"""Settings API —— 前端设置界面的后端支撑。

- GET  /api/settings      返回分组配置（API Key 脱敏）
- PUT  /api/settings      合并更新（即时生效 + 持久化 .env）
- POST /api/settings/test 验证文本 / 生图接口连通性
"""
from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Request

from app.config_store import grouped, update as cfg_update, requires_settings_token
from app.llm.agnes import agnes, AgnesError
from app.tools import ToolRegistry

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    changes: dict[str, str] = {}


class SettingsTest(BaseModel):
    target: str = "text"  # "text" | "image"


def _assert_token(request: Request) -> None:
    """若已配置 SETTINGS_API_TOKEN，则写接口必须携带正确令牌。

    接受两种方式：``Authorization: Bearer <token>`` 或 ``X-Settings-Token: <token>``
    （也兼容 ``?token=`` 查询参数，便于简单调试）。
    """
    if not requires_settings_token():
        return
    expected = cfg_token()
    provided = (
        (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
        or request.headers.get("x-settings-token", "").strip()
        or (request.query_params.get("token") or "").strip()
    )
    if not provided or provided != expected:
        raise HTTPException(status_code=401, detail="设置受保护：请提供正确的 X-Settings-Token")


def cfg_token() -> str:
    from app.config_store import get
    return get("SETTINGS_API_TOKEN", "")


@router.get("")
def get_settings():
    return {"groups": grouped(), "runtime": True}


@router.get("/status")
def settings_status():
    """前端据此判断是否需要展示设置保护令牌输入框。"""
    return {"requires_token": requires_settings_token()}


@router.put("")
def put_settings(body: SettingsUpdate, request: Request):
    _assert_token(request)
    cfg_update(body.changes)
    return {"ok": True, "groups": grouped()}


@router.post("/test")
def test_settings(body: SettingsTest, request: Request):
    """轻量连通性验证：真实打一发最小化请求，返回 ok/error。"""
    _assert_token(request)
    if body.target == "text":
        if not agnes.enabled():
            return {"target": "text", "ok": False, "detail": "未配置 AGNES_API_KEY"}
        try:
            # 最小化探测：要求返回极短文本
            out = agnes.chat(
                [{"role": "user", "content": "reply with the single word: ok"}],
                temperature=0, max_tokens=8,
            )
            return {"target": "text", "ok": True, "detail": (out or "").strip()[:40]}
        except AgnesError as e:
            return {"target": "text", "ok": False, "detail": str(e)[:200]}
        except Exception as e:  # noqa: BLE001
            return {"target": "text", "ok": False, "detail": f"请求异常: {e}"[:200]}

    # image
    backend = ToolRegistry.get("image_generation")
    try:
        res = backend.run({
            "product_name": "connectivity-test", "niche_keyword": "test",
            "style": "ecommerce", "count": 1, "platform": "amazon",
        })
        imgs = res.get("images", []) if isinstance(res, dict) else []
        failed = sum(1 for i in imgs if "失败" in (i.get("description") or ""))
        if failed == len(imgs) and imgs:
            return {"target": "image", "ok": False,
                    "detail": (imgs[0].get("description") or "")[:200]}
        return {"target": "image", "ok": True,
                "detail": f"已路由到 {backend.backend_type.value} 后端，返回 {len(imgs)} 张方案"}
    except Exception as e:  # noqa: BLE001
        return {"target": "image", "ok": False, "detail": f"请求异常: {e}"[:200]}
