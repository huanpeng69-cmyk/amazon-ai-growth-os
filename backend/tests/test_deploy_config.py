"""P0-4 部署配置守护测试。

不依赖 Docker 守护进程即可在 CI 中运行，用来防止部署产物回退：
- gunicorn.conf.py 关键参数正确（worker_class / workers / bind / 超时）；
- requirements.lock 存在且对核心依赖使用精确 `==` 锁定；
- gunicorn CMD 里引用的应用入口 `app.main:app` 真实可导入。
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

# backend/ 目录（本文件位于 backend/tests/）
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


def _load_gunicorn_conf():
    """gunicorn.conf.py 含点号不是合法模块名，用文件路径动态加载。"""
    conf_path = BACKEND_DIR / "gunicorn.conf.py"
    assert conf_path.exists(), f"缺少 {conf_path}"
    spec = importlib.util.spec_from_file_location("gunicorn_conf", conf_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_gunicorn_uses_uvicorn_worker():
    conf = _load_gunicorn_conf()
    assert conf.worker_class == "uvicorn.workers.UvicornWorker"


def test_gunicorn_sane_defaults():
    conf = _load_gunicorn_conf()
    assert conf.workers >= 1
    assert conf.bind.startswith("0.0.0.0:")          # 容器内对外监听
    assert conf.timeout >= 60                          # 给 agent 外部调用留足时间
    assert conf.accesslog == "-" and conf.errorlog == "-"  # 日志走 stdout/stderr


def test_gunicorn_workers_env_override(monkeypatch):
    monkeypatch.setenv("WEB_CONCURRENCY", "7")
    conf = _load_gunicorn_conf()
    assert conf.workers == 7


def test_requirements_lock_pins_core_deps():
    lock = ROOT_DIR / "requirements.lock"
    assert lock.exists(), "缺少 requirements.lock（可复现构建依赖）"
    text = lock.read_text(encoding="utf-8")
    for pkg in ("fastapi", "uvicorn", "gunicorn", "starlette", "pydantic", "SQLAlchemy"):
        # 允许 uvicorn[standard] 这样的 extras 形式
        pattern = rf"(?im)^{re.escape(pkg)}(\[[^\]]+\])?==\S+"
        assert re.search(pattern, text), f"requirements.lock 未用 == 锁定 {pkg}"


def test_dockerfile_and_compose_exist():
    assert (ROOT_DIR / "Dockerfile").exists()
    assert (ROOT_DIR / "docker-compose.yml").exists()
    assert (ROOT_DIR / ".dockerignore").exists()


def test_app_entrypoint_importable():
    """gunicorn CMD 引用的 app.main:app 必须真实存在且可导入。"""
    from app.main import app  # noqa: F401
    assert app is not None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
