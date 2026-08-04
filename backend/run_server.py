"""Amazon AI Growth OS 启动器。

自动从 8000 起寻找可用端口并启动 uvicorn，避免端口被旧进程占用时启动失败。
用法（由 start.bat 调用，已处于 backend 目录且激活 venv）：
    python run_server.py
"""
from __future__ import annotations

import socket
import uvicorn


def find_free_port(start: int = 8000, end: int = 8020) -> int:
    """从 start 到 end 找到第一个可绑定的本地端口。"""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"在 {start}-{end} 范围内未找到可用端口")


if __name__ == "__main__":
    port = find_free_port(8000, 8020)
    print("[start] Amazon AI Growth OS 已启动")
    print(f"[start] 请在浏览器打开: http://127.0.0.1:{port}/")
    print(f"[start] 视觉工厂页: http://127.0.0.1:{port}/#/visual")
    print("[start] 按 Ctrl+C 停止服务")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=False)
