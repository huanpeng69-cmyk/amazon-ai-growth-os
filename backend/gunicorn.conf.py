"""Gunicorn 生产配置（供 Docker 部署）。

全部参数由环境变量驱动，便于在 compose / K8s 中调优而无需改镜像。
启动命令（见 Dockerfile CMD）：
    gunicorn app.main:app -c gunicorn.conf.py
"""
from __future__ import annotations

import os

# 监听地址：容器内固定 0.0.0.0，端口由 PORT 覆盖
bind = os.getenv("BIND", f"0.0.0.0:{os.getenv('PORT', '8000')}")

# worker 数：默认 2；生产建议 (2*CPU)+1，通过 WEB_CONCURRENCY 注入
workers = int(os.getenv("WEB_CONCURRENCY", "2"))

# 用 Uvicorn 的 ASGI worker 跑 FastAPI（异步）
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "uvicorn.workers.UvicornWorker")

# 单次请求超时（秒）：agent 链路调用外部（Bright Data+LLM）可能 30–60s，留足余量。
# 注：请求级细粒度超时由 P1-4 处理，此处为 worker 级兜底。
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# 周期性回收 worker，缓解潜在内存增长（带抖动避免同时重启）
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

# 日志输出到 stdout/stderr（容器友好，交由 Docker/编排采集）
loglevel = os.getenv("LOG_LEVEL", "info")
accesslog = "-"
errorlog = "-"

# 让 X-Forwarded-For 生效（限流按真实客户端 IP，见 app/ratelimit.py）
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "*")
