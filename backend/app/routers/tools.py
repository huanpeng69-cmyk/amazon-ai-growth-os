"""Tool 层 HTTP 接口：列出契约、查看契约、执行工具。

Agent / 前端通过本路由统一调用 MCP Tool 层，不直接依赖具体后端实现。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.tools import ToolRegistry
from app.tools.base import ToolError, ToolNotConfigured

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolRunRequest(BaseModel):
    input: dict
    backend: str | None = None  # 可选：临时覆盖后端（mock/mcp/api/local_model）


@router.get("")
def list_tools():
    return {"tools": [ToolRegistry.describe(n) for n in ToolRegistry.names()]}


@router.get("/{name}")
def describe_tool(name: str):
    if name not in ToolRegistry.names():
        raise HTTPException(status_code=404, detail=f"未找到工具 {name}")
    return ToolRegistry.describe(name)


@router.post("/{name}")
def run_tool(name: str, req: ToolRunRequest):
    if name not in ToolRegistry.names():
        raise HTTPException(status_code=404, detail=f"未找到工具 {name}")
    try:
        tool = ToolRegistry.get(name, req.backend)
        result = tool.run(req.input)
    except ToolNotConfigured as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except ToolError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"未找到工具 {name}")
    return {"tool": name, "backend": tool.backend_type.value, "result": result}
