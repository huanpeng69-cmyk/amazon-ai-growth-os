"""内容安全策略（CSP）中间件。

仅在生产环境（APP_ENV == "production"）注入，避免破坏本地 Vite 开发服务器
（5173 端口的 HMR 会注入内联脚本，严格 CSP 会误伤；本地用源码直跑也不需 CSP）。

策略取舍（诚实说明）：
- 源码 SPA 使用「全局脚本」风格，且 views.js 里存在若干由应用自身代码写入的
  内联事件处理器（onclick= / onerror=）。这些是**受控代码**而非不可信用户输入，
  因此 script-src / style-src 保留 'unsafe-inline'，以保证功能不被破坏。
- 真正的安全增益来自：禁止从外部源加载脚本（script-src 不含 http/https 通配）、
  收紧 connect-src（仅同源，阻断数据外泄）、object-src 'none'、base-uri 'self' 等。
- 后续若要进一步收紧（去掉 'unsafe-inline'），需把 views.js 的内联处理器改为
  addEventListener 绑定，再配合 nonce 或严格 src。
"""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# 允许通过环境变量追加额外源（如自定义 CDN / 字体），逗号分隔。
_EXTRA = [o.strip() for o in os.getenv("CSP_EXTRA_SOURCES", "").split(",") if o.strip()]

# 默认策略：同源优先，外部仅放开 Google Fonts（字体 + 字体 CSS 宿主）。
_FONT_HOSTS = ["fonts.googleapis.com", "fonts.gstatic.com"]
_ALLOWED_EXTERNAL = sorted(set(_FONT_HOSTS + _EXTRA))

# 组装 CSP 指令。'unsafe-inline' 仅用于 script/style（见模块 docstring 说明）。
def _build_policy() -> str:
    ext = " ".join(_ALLOWED_EXTERNAL)
    # 图片允许 data:（内联 SVG/图表）与 https:（外部商品图）；连接仅同源。
    img = f"'self' data: https: {ext}".strip()
    connect = f"'self' {ext}".strip()
    directives = [
        "default-src 'self'",
        # 受控内联处理器需要 'unsafe-inline'；不放开外部脚本源
        "script-src 'self' 'unsafe-inline'",
        # style-src 放开 Google Fonts 的 CSS 宿主（fonts.googleapis.com），
        # 否则 <link rel=stylesheet> 会被拦截、生产环境字体回退为系统字体。
        f"style-src 'self' 'unsafe-inline' {ext}".rstrip(),
        f"font-src 'self' {ext}".rstrip(),
        f"img-src {img}",
        f"connect-src {connect}",
        "frame-src 'none'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
    return "; ".join(d for d in directives if d)


_CSP_VALUE = _build_policy()


class CSPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # 仅在尚未设置时注入（避免覆盖更上层的覆盖逻辑）
        if "content-security-policy" not in response.headers:
            response.headers["Content-Security-Policy"] = _CSP_VALUE
        return response
