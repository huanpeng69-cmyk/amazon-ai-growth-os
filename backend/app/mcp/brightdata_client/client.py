"""Bright Data MCP 客户端（JSON-RPC 2.0 over HTTP，纯标准库实现）。

设计要点
--------
1. **零依赖**：项目 venv 当前没有 mcp / httpx / requests，因此传输层用
   ``http.client`` + ``json`` + ``urllib`` 手写，不引入任何第三方包。
2. **可注入 transport**：``BrightDataMCPClient`` 接收一个 ``Transport`` 对象。
   默认是 ``StreamableHttpTransport``（POST JSON-RPC，兼容 text/event-stream 响应）；
   测试时注入 ``MockTransport`` 即可离线验证 **Agent ↓ Tool ↓ MCP ↓ Bright Data** 全链路。
3. **流式(SSE)兼容**：部分 MCP 端点以 ``text/event-stream`` 返回，传输层会把
   ``data:`` 帧还原成 JSON 对象。
4. **会话保持**：``initialize`` 返回的 ``Mcp-Session-Id`` 会回写后续请求头。
5. **统一返回**：``call_tool`` 自动把 ``result.content[].text`` 解析为 Python 对象
   （能 JSON 解析就解析，否则保留原始文本）。

调用链（架构约束）：Agent → Tool(mcp.tools.*) → MCP(client) → Bright Data。
本客户端**只**被 mcp.tools 调用，Agent 永不直接触达 Bright Data。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.config_store import get as config_get
from app.mcp.brightdata_client.exceptions import (
    BrightDataAuthError,
    BrightDataError,
    BrightDataProtocolError,
    BrightDataToolError,
    BrightDataToolNotFound,
    BrightDataTransportError,
)


# ───────────────────────── Transport 抽象 ─────────────────────────
class Transport:
    """传输层契约：request(payload) -> JSON-RPC 响应 dict。

    实现类负责把 JSON-RPC 请求发到 Bright Data MCP 端点并取回响应。
    """

    def request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


def _extract_sse_json(body: str) -> Dict[str, Any]:
    """从 text/event-stream 正文里取最后一个 ``data:`` 帧并解析为 JSON。

    退化情况：若整段本身就是 JSON，直接解析。
    """
    body = body.strip()
    if not body:
        raise BrightDataProtocolError("Bright Data 返回空响应")
    if body.startswith("{"):
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:  # pragma: no cover - 边界
            raise BrightDataProtocolError(f"JSON 解析失败：{e}") from e
    last = None
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data = line[len("data:"):].strip()
            if data and data != "[DONE]":
                last = data
    if last is None:
        raise BrightDataProtocolError("SSE 响应中未发现 data 帧")
    try:
        return json.loads(last)
    except json.JSONDecodeError as e:
        raise BrightDataProtocolError(f"SSE data 帧 JSON 解析失败：{e}") from e


class StreamableHttpTransport(Transport):
    """Streamable HTTP 传输（Anthropic 2025 MCP 规范）。

    对端点 URL 做一次 ``initialize`` 握手，拿到 ``Mcp-Session-Id`` 后复用；
    后续 ``tools/list`` / ``tools/call`` 复用同一会话。
    """

    def __init__(self, endpoint: str, api_key: str, timeout: float = 60.0):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session_id: Optional[str] = None

    def _headers(self) -> Dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        import http.client
        from urllib.parse import urlparse

        if not self.api_key:
            raise BrightDataAuthError()
        parsed = urlparse(self.endpoint)
        host = parsed.hostname or "mcp.brightdata.com"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        raw_body = json.dumps(payload).encode("utf-8")
        try:
            if parsed.scheme == "https":
                conn = http.client.HTTPSConnection(host, port, timeout=self.timeout)
            else:
                conn = http.client.HTTPConnection(host, port, timeout=self.timeout)
            conn.request("POST", path, body=raw_body, headers=self._headers())
            resp = conn.getresponse()
        except (OSError, http.client.HTTPException) as e:
            raise BrightDataTransportError(f"连接 Bright Data 失败：{e}") from e
        try:
            status = resp.status
            body = resp.read().decode("utf-8", "replace")
            # 捕获会话 ID（initialize 响应头）
            sid = resp.getheader("Mcp-Session-Id")
            if sid:
                self.session_id = sid
        finally:
            conn.close()
        if status in (401, 403):
            raise BrightDataAuthError(f"HTTP {status}")
        if status >= 400:
            raise BrightDataTransportError(f"HTTP {status}：{body[:500]}")
        try:
            return _extract_sse_json(body)
        except BrightDataProtocolError:
            # 有些端点返回纯文本错误信息
            raise BrightDataProtocolError(f"无法解析响应（HTTP {status}）：{body[:500]}")

    def request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(payload)


class MockTransport(Transport):
    """离线测试 transport：按 method 返回预置响应，可注入。

    用法：
        transport = MockTransport()
        transport.on("tools/list", lambda p: {"tools": [...]})
        transport.on("tools/call", lambda p: {"content": [{"type":"text","text": json.dumps(...)}]})
    """

    def __init__(self, handlers: Optional[Dict[str, Any]] = None):
        self._handlers: Dict[str, Any] = dict(handlers or {})
        self.last_payload: Optional[Dict[str, Any]] = None

    def on(self, method: str, handler) -> "MockTransport":
        self._handlers[method] = handler
        return self

    def request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.last_payload = payload
        method = payload.get("method")
        handler = self._handlers.get(method)
        if handler is None:
            # 默认给出最小合法 JSON-RPC 响应
            return {"jsonrpc": "2.0", "id": payload.get("id"), "result": {}}
        result = handler(payload) if callable(handler) else handler
        if isinstance(result, dict) and "jsonrpc" not in result:
            result = {"jsonrpc": "2.0", "id": payload.get("id"), "result": result}
        return result


# ───────────────────────── MCP 客户端 ─────────────────────────
class BrightDataMCPClient:
    """Bright Data MCP 客户端。

    典型用法（live）：
        client = BrightDataMCPClient()           # 从 config_store 读凭证
        tools = client.list_tools()
        out = client.call_tool("amazon_search", {"keyword": "cat water fountain"})

    测试用法（离线）：
        client = BrightDataMCPClient(transport=MockTransport(...))
    """

    DEFAULT_ENDPOINT = "https://mcp.brightdata.com/mcp"

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        transport: Optional[Transport] = None,
        timeout: float = 60.0,
        auto_init: bool = True,
    ):
        self.api_key = api_key if api_key is not None else config_get("BRIGHTDATA_API_KEY", "")
        self.endpoint = endpoint or config_get("BRIGHTDATA_ENDPOINT", self.DEFAULT_ENDPOINT)
        self.timeout = timeout
        self._transport = transport or StreamableHttpTransport(
            self.endpoint, self.api_key, timeout
        )
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        if auto_init and not isinstance(self._transport, MockTransport):
            try:
                self._initialize()
            except BrightDataError:
                # 某些端点允许免 initialize 直接调用；保留异常由调用方决定
                raise

    # —— 底层 JSON-RPC ——
    def _rpc(self, method: str, params: Dict[str, Any], req_id: int = 1) -> Dict[str, Any]:
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        try:
            resp = self._transport.request(payload)
        except BrightDataError:
            raise
        except Exception as e:  # pragma: no cover - 防御
            raise BrightDataTransportError(f"未知传输错误：{e}") from e
        if not isinstance(resp, dict):
            raise BrightDataProtocolError("响应不是 JSON 对象")
        if "error" in resp and resp["error"] is not None:
            err = resp["error"]
            msg = (err.get("message") if isinstance(err, dict) else str(err)) or "unknown"
            code = err.get("code") if isinstance(err, dict) else None
            if code in (401, 403) or "unauthorized" in msg.lower():
                raise BrightDataAuthError(msg)
            raise BrightDataToolError(f"[{code}] {msg}")
        if "result" not in resp:
            raise BrightDataProtocolError(f"响应缺少 result 字段：{resp}")
        return resp

    def _initialize(self) -> Dict[str, Any]:
        return self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "amazon-ai-growth-os", "version": "1.0.0"},
            },
        ).get("result", {})

    # —— 公共 API ——
    def list_tools(self, force: bool = False) -> List[Dict[str, Any]]:
        if self._tools_cache is not None and not force:
            return self._tools_cache
        resp = self._rpc("tools/list", {})
        tools = (resp.get("result") or {}).get("tools", [])
        self._tools_cache = tools
        return tools

    def resolve_tool(self, *candidates: str) -> str:
        """按候选名匹配服务端可用工具（子串不区分大小写）。

        找不到时抛 BrightDataToolNotFound（携带可用工具名，便于排查）。
        """
        available = self.list_tools()
        names = [t.get("name", "") for t in available]
        for cand in candidates:
            for n in names:
                if cand and cand.lower() in n.lower():
                    return n
        raise BrightDataToolNotFound(list(candidates), names)

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """调用工具，返回解析后的内容（dict / list / str）。

        Bright Data 的 ``tools/call`` 结果形如
        ``{"content":[{"type":"text","text":"<json 或 markdown>"}],"isError":false}``，
        这里自动把 text 解析为 Python 对象（能解析就解析）。
        """
        resp = self._rpc("tools/call", {"name": name, "arguments": arguments})
        result = resp.get("result")
        if isinstance(result, dict) and result.get("isError"):
            text = self._content_text(result)
            raise BrightDataToolError(text or "未知工具错误", tool=name)
        return self._content_text(result)

    # —— 解析辅助 ——
    @staticmethod
    def _content_text(result: Any) -> Any:
        """从 tools/call 的 result 抽取内容：优先解析 content[].text 为 JSON。"""
        if not isinstance(result, dict):
            return result
        content = result.get("content")
        if isinstance(content, list) and content:
            # 拼接所有 text 类型帧
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            joined = "\n".join(t for t in texts if t)
            if not joined:
                # 非文本（如 image）：原样返回结构化内容
                return result
            return _try_json(joined)
        # 部分服务端直接把结果放在 result 顶层
        if "text" in result:
            return _try_json(result["text"])
        return result


def _try_json(s: str) -> Any:
    s = s.strip()
    if not s:
        return s
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return s
