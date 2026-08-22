"""image_generation 后端适配器。

- MockImageGenBackend：返回确定性的电商图片方案（场景/比例/提示词），离线可演示。
- ApiImageGenBackend：接入 WisArt 文生图（智画创），OpenAI 兼容约定，配置驱动。
- LocalModelImageGenBackend / McpImageGenBackend：预留 SDXL 本地推理 / ecom-details-image MCP。
"""
from __future__ import annotations

from app.tools.base import BackendType, ToolBackend, ToolNotConfigured

# 电商主图/附图标准场景（首图白底 1:1，其余 3:4 信息图）
_SCENES: list[tuple[str, str, str]] = [
    ("主图白底", "1:1", "纯白背景产品主图，居中展示，高清细节，符合平台主图规范"),
    ("使用场景", "3:4", "真实生活场景中使用产品，突出核心使用方式与人群"),
    ("细节特写", "3:4", "关键功能/材质特写，放大展示差异化卖点"),
    ("痛点对比", "3:4", "使用前 vs 使用后的对比图，直观呈现解决的问题"),
    ("尺寸规格", "3:4", "尺寸对照/规格信息图，消除购买犹豫"),
    ("生活方式", "3:4", "品牌调性生活方式图，强化情感与信任"),
    ("信任背书", "1:1", "评分/认证/与竞品对比优势图，建立购买信任"),
]


class MockImageGenBackend(ToolBackend):
    backend_type = BackendType.MOCK

    def execute(self, params: dict) -> dict:
        n = max(1, min(params.get("count", 4), len(_SCENES)))
        scenes = _SCENES[:n]
        images = []
        for i, (scene, ratio, desc) in enumerate(scenes):
            images.append({
                "scene": scene,
                "aspect_ratio": ratio,
                "prompt": (
                    f"Professional Amazon {params['platform']} product photo of "
                    f"{params['product_name']}, {scene}, {params['niche_keyword']} niche, "
                    f"studio lighting, high detail, {params.get('style', 'ecommerce')} style"
                ),
                "description": f"为「{params['product_name']}」生成{desc}。",
            })
        return {
            "product_name": params["product_name"],
            "platform": params["platform"],
            "images": images,
        }


class ApiImageGenBackend(ToolBackend):
    """WisArt 文生图后端（智画创 · https://wisart.kuaileshifu.com）。

    会员 API 文档需登录后查看：https://wisart.kuaileshifu.com/#/member/api-docs
    下方按 OpenAI 兼容约定（POST {base}{endpoint}，Bearer 鉴权，返回 data[].url/b64_json）
    实现，可覆盖绝大多数合规 WisArt 端点；若 WisArt 实际为「异步任务」接口
    （submit 拿到 task_id 再 query 拿图），请把 WISART_ASYNC=1 并改写 _wisart_call。

    配置（环境变量）：
      WISART_API_KEY      必填；未设置则抛出 ToolNotConfigured（前端/兜底不受影响）。
      WISART_BASE_URL     默认 https://wisart.kuaileshifu.com/api
      WISART_ENDPOINT     默认 /v1/images/generations
      WISART_AUTH_SCHEME  默认 Bearer；若是 X-API-Key 等自定义头请改成对应头名。
    """

    backend_type = BackendType.API

    def execute(self, params: dict) -> dict:
        import os
        from concurrent.futures import ThreadPoolExecutor, as_completed

        api_key = os.getenv("WISART_API_KEY", "")
        if not api_key:
            raise ToolNotConfigured(
                "image_generation API 后端未配置：设置 WISART_API_KEY 与 WISART_BASE_URL "
                "（默认 https://wisart.kuaileshifu.com）接入 WisArt 文生图。"
            )
        base = os.getenv("WISART_BASE_URL", "https://wisart.kuaileshifu.com").rstrip("/")
        endpoint = os.getenv("WISART_ENDPOINT", "/v1/images/generations")
        auth_scheme = os.getenv("WISART_AUTH_SCHEME", "Bearer")
        model = os.getenv("WISART_MODEL", "gpt-image-2")
        is_async = os.getenv("WISART_ASYNC", "0") == "1"
        timeout = int(os.getenv("WISART_TIMEOUT", "120") or 120)

        n = max(1, min(params.get("count", 7), len(_SCENES)))
        scenes = _SCENES[:n]
        # 外部传入的逐张 Prompt（来自视觉规划，已按槽位差异化）；有则用，无则回退模板
        external_prompts = params.get("prompts") or []

        def _gen(i: int):
            scene, ratio, desc = scenes[i]
            ext = external_prompts[i] if i < len(external_prompts) else ""
            if ext and ext.strip():
                # 用视觉规划为该槽位精心撰写的差异化 Prompt（展示即真实生图 Prompt）
                prompt = ext.strip()
            else:
                prompt = (
                    f"Professional Amazon {params['platform']} product photo of "
                    f"{params['product_name']}, {params['niche_keyword']} niche, {scene}, "
                    f"{params.get('style', 'ecommerce')} style, high detail, studio lighting"
                )
            image_url = None
            note = ""
            try:
                if is_async:
                    link, note = self._wisart_call_async(base, endpoint, auth_scheme, api_key, prompt, model)
                else:
                    link, note = self._wisart_call_sync(base, endpoint, auth_scheme, api_key, prompt, model, timeout)
                image_url = link
                desc_txt = f"WisArt 已生成「{params['product_name']}」{scene}（{ratio}）。" + (
                    f" 链接：{link}" if link else (f" {note}" if note else ""))
            except Exception as e:
                desc_txt = f"WisArt 调用失败（{e}）；保留生成请求，待重试。"
            return i, {
                "scene": scene,
                "aspect_ratio": ratio,
                "prompt": prompt,
                "description": desc_txt,
                "image_url": image_url,  # 真实图片 URL（WisArt 返回）或 None
            }

        # 并发调用 WisArt（每张图推理耗时数十秒，串行会超时）；限制并发避免触发限流
        images = [None] * n
        max_workers = min(n, 5)
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_gen, i) for i in range(n)]
            for fut in as_completed(futures):
                i, item = fut.result()
                images[i] = item
        return {
            "product_name": params["product_name"],
            "platform": params["platform"],
            "images": images,
        }

    @staticmethod
    def _wisart_call_sync(base, endpoint, auth_scheme, api_key, prompt, model="gpt-image-2", timeout=120):
        import json
        import urllib.error
        import urllib.request
        url = base + endpoint
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
            "response_format": "url",
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if auth_scheme.lower() == "bearer":
            req.add_header("Authorization", f"Bearer {api_key}")
        else:
            req.add_header(auth_scheme, api_key)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            return None, f"HTTP {e.code}: {detail}"
        except urllib.error.URLError as e:
            return None, f"网络错误: {e.reason}"
        item = (data.get("data") or [{}])[0] if isinstance(data, dict) else {}
        link = item.get("url")
        if not link and item.get("b64_json"):
            link = "data:image/png;base64," + item["b64_json"]
        return link, ""

    @staticmethod
    def _wisart_call_async(base, endpoint, auth_scheme, api_key, prompt, model="gpt-image-2"):
        """异步任务占位：submit 后轮询 query。请在获知 WisArt 真实契约后补全。"""
        raise ToolNotConfigured(
            "WisArt 异步任务接口未实现：请参照登录后的会员 API 文档补全 submit/query 逻辑。"
        )


class AgnesImageGenBackend(ToolBackend):
    """Agnes AI 文生图后端（OpenAI 兼容 /images/generations）。

    复用已配置的 AgnesClient（agnes.py 单例），当 AGNES_API_KEY 已设置时
    直接调用 agnes.generate_image(prompt) 获取真实图片 URL / base64。
    无 Key 时回退占位说明（保证离线可用，且不伪造真实图片）。
    """
    backend_type = BackendType.AGNES  # 通过配置 TOOL_BACKEND_IMAGE_GENERATION=agnes 激活

    def execute(self, params: dict) -> dict:
        from app.llm.agnes import agnes as _agnes_client

        n = max(1, min(params.get("count", 4), len(_SCENES)))
        scenes = _SCENES[:n]
        images = []
        has_agnes = _agnes_client.enabled()

        for i, (scene, ratio, desc) in enumerate(scenes):
            prompt = (
                f"Professional Amazon {params['platform']} product photo of "
                f"{params['product_name']}, {scene}, {params['niche_keyword']} niche, "
                f"{params.get('style', 'ecommerce')} style, high detail, studio lighting"
            )
            image_url = None
            note = ""

            if has_agnes:
                try:
                    results = _agnes_client.generate_image(prompt, size="1024x1024", n=1)
                    if results:
                        item = results[0]
                        image_url = item.get("url") or (
                            f"data:image/png;base64,{item['b64_json']}" if item.get("b64_json") else None
                        )
                    if not image_url:
                        note = "Agnes 返回空结果，使用占位"
                except Exception as e:
                    note = f"Agnes 生图失败({e})，使用占位"
            else:
                note = "AGNES_API_KEY 未配置，显示占位（请在设置页填入 Key 启用真实生图）"

            images.append({
                "scene": scene,
                "aspect_ratio": ratio,
                "prompt": prompt,
                "description": f"为「{params['product_name']}」生成{desc}。" + (f" {note}" if note else ""),
                "image_url": image_url,  # 真实图片 URL 或 None
            })

        return {
            "product_name": params["product_name"],
            "platform": params["platform"],
            "images": images,
        }


class LocalModelImageGenBackend(ToolBackend):
    backend_type = BackendType.LOCAL_MODEL

    def execute(self, params: dict) -> dict:
        raise ToolNotConfigured(
            "image_generation 本地模型后端未配置：接入 SDXL / FLUX 本地推理"
        )


class McpImageGenBackend(ToolBackend):
    backend_type = BackendType.MCP

    def execute(self, params: dict) -> dict:
        cmd = self.config.get("server_command") or "ecom-details-image-mcp"
        raise ToolNotConfigured(
            "image_generation MCP 后端未接入：请补全 ecom-details-image MCP 的 "
            f"generate_image_plan 调用（server={cmd}）。"
        )
