# syntax=docker/dockerfile:1
# ============================================================
# Amazon AI Growth OS · 生产镜像
# 一条命令构建并运行：
#     docker build -t amazon-ai-growth-os .
#     docker run --rm -p 8000:8000 amazon-ai-growth-os
# 打开 http://127.0.0.1:8000/  （健康检查 /api/health）
# ============================================================

# —— 阶段 1：前端生产构建（minify + 内容哈希）——
FROM node:20-alpine AS frontend-build
WORKDIR /fe
# 先装依赖以最大化层缓存
COPY frontend/package.json ./package.json
COPY frontend/package-lock.json ./package-lock.json
RUN npm ci --no-audit --no-fund
# 再拷源码并构建（产出 frontend/dist/）
COPY frontend/ ./frontend
RUN cd frontend && npm run build

# —— 阶段 2：Python 运行时 ——
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    WEB_CONCURRENCY=2

WORKDIR /app

# 1) 先只拷贝锁定文件安装依赖 —— 最大化 Docker 层缓存（代码改动不触发重装）
COPY requirements.lock ./requirements.lock
RUN pip install -r requirements.lock

# 2) 创建非 root 运行用户
RUN useradd --create-home --uid 10001 appuser

# 3) 拷贝后端代码与前端静态资源
#    - backend/ 完整拷贝
#    - 前端仅拷贝「已构建产物」frontend/dist（来自前端构建阶段），不再带源码
COPY backend/ ./backend/
COPY --from=frontend-build /fe/frontend/dist ./frontend/dist

# 4) 运行时数据目录（SQLite 落盘点，可用卷持久化）
RUN mkdir -p /app/backend/data && chown -R appuser:appuser /app

USER appuser
WORKDIR /app/backend
EXPOSE 8000

# 容器健康检查：命中 /api/health（无需额外工具，用 stdlib urllib）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status==200 else 1)"

# gunicorn + UvicornWorker 多 worker（生产 ASGI 服务器；参数见 gunicorn.conf.py）
CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]
