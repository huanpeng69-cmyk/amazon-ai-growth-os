"""Agnes AI 客户端（OpenAI 兼容）。

文档：https://www.agnes-ai.com/zh-Hans/docs/overview
- Base URL: https://apihub.agnes-ai.com/v1
- 认证:    Authorization: Bearer <AGNES_API_KEY>
- 文本:    POST /v1/chat/completions
- 图像:    POST /v1/images/generations

环境变量（均可在运行时注入，无需改代码）：
  AGNES_API_KEY      必填（设置后才启用真实调用；未设置则相关能力走启发式/兜底）
  AGNES_BASE_URL     默认 https://apihub.agnes-ai.com/v1
  AGNES_TEXT_MODEL   文本模型 ID（在 Agnes 控制台查看真实 ID；默认 agnes-gpt-4o）
  AGNES_IMAGE_MODEL  图像模型 ID（默认 agnes-sd）
  AGNES_TIMEOUT      单次请求超时（秒），默认 60
"""
from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request

from app.config_store import get as _cfg

DEFAULT_BASE_URL = "https://apihub.agnes-ai.com/v1"


class AgnesError(RuntimeError):
    """Agnes API 调用错误（网络/HTTP/解析）。"""


class AgnesClient:
    """配置在调用时从 config_store 读取，因此前端改配置即时生效。"""

    @property
    def api_key(self) -> str:
        return _cfg("AGNES_API_KEY", "")

    @property
    def base_url(self) -> str:
        return _cfg("AGNES_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

    @property
    def text_model(self) -> str:
        return _cfg("AGNES_TEXT_MODEL", "agnes-gpt-4o")

    @property
    def image_model(self) -> str:
        return _cfg("AGNES_IMAGE_MODEL", "agnes-sd")

    @property
    def timeout(self) -> int:
        return int(_cfg("AGNES_TIMEOUT", "60") or 60)

    def enabled(self) -> bool:
        """是否已配置真实调用（有 API Key 才启用）。"""
        return bool(self.api_key)

    def chat(self, messages: list[dict], *, model: str | None = None,
             temperature: float = 0.7, max_tokens: int = 1200) -> str:
        if not self.enabled():
            raise AgnesError("AGNES_API_KEY 未设置，无法调用真实文本模型")
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model or self.text_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = self._post(url, payload)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise AgnesError(f"Agnes 文本响应格式异常: {e} | raw={data}") from e

    def generate_image(self, prompt: str, *, model: str | None = None,
                       size: str = "1024x1024", n: int = 1) -> list[dict]:
        if not self.enabled():
            raise AgnesError("AGNES_API_KEY 未设置，无法调用真实图像模型")
        url = f"{self.base_url}/images/generations"
        payload = {
            "model": model or self.image_model,
            "prompt": prompt,
            "size": size,
            "n": n,
        }
        data = self._post(url, payload)
        items = data.get("data", [])
        out: list[dict] = []
        for it in items:
            out.append({"url": it.get("url"), "b64_json": it.get("b64_json")})
        return out

    # —— 内部 ——
    def _post(self, url: str, payload: dict) -> dict:
        """POST 到 Agnes，对瞬时网络/5xx 错误自动重试。

        关键：任何失败（含 http.client.RemoteDisconnected、URLError、OSError、
        JSON 解析失败）都统一包装为 AgnesError，绝不向调用方抛出裸网络异常，
        从而保证上层 except AgnesError 的降级逻辑一定能被触发（不会 500）。
        """
        body = json.dumps(payload).encode("utf-8")
        last_err: Exception | None = None
        for _ in range(3):  # 1 次原请求 + 2 次重试，扛过瞬时断开/限流
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                # 4xx 客户端错误（401/403/400）重试无意义，直接抛
                if e.code != 429 and e.code < 500:
                    detail = e.read().decode("utf-8", "ignore")[:500]
                    raise AgnesError(f"Agnes API HTTP {e.code}: {detail}") from e
                last_err = e  # 429 / 5xx 可重试
                continue
            except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
                # 含 RemoteDisconnected、连接重置、DNS/超时等瞬时网络错误
                last_err = e
                continue
            except json.JSONDecodeError as e:
                last_err = e
                continue
        raise AgnesError(f"Agnes API 调用失败（重试 3 次仍失败）: {last_err}") from last_err


# 模块级单例（配置运行时可变，调用时读取最新值）
agnes = AgnesClient()

