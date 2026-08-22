"""P2-4 配置校验测试。

锁定：app/config.py 经 pydantic-settings 校验，非法配置在导入期即 fail-fast，
既有的模块级常量（from app.config import X）行为向后兼容。
"""
from __future__ import annotations

import importlib
import os

import pytest
from pydantic import ValidationError

from app.config import Settings, AGENT_TIMEOUT_SECONDS, RESEARCH_CACHE_TTL_SECONDS


def test_defaults_are_sane_and_backward_compatible():
    """默认常量符合既有契约（cache.py / database.py / timeout.py 依赖）。"""
    import app.config as cfg

    assert AGENT_TIMEOUT_SECONDS == 120
    assert cfg.REQUEST_TIMEOUT_SECONDS == 300
    assert RESEARCH_CACHE_TTL_SECONDS == 600
    assert cfg.RESEARCH_CACHE_MAXSIZE == 256
    assert cfg.CANDIDATE_POOL_SIZE == 24
    assert cfg.TOP_N == 10
    assert cfg.APP_ENV == "demo"
    assert cfg.DATABASE_URL.startswith("sqlite:///")


def test_settings_class_reads_explicit_override():
    """通过构造参数覆盖（等价环境变量）时生效。"""
    s = Settings(AGENT_TIMEOUT_SECONDS=5, RESEARCH_CACHE_TTL_SECONDS=0)
    assert s.AGENT_TIMEOUT_SECONDS == 5
    assert s.RESEARCH_CACHE_TTL_SECONDS == 0  # TTL=0 关闭缓存属合法值


def test_invalid_int_rejected():
    """非整数字符串必须被校验拦下（否则 int(os.getenv(...)) 会在运行时崩溃）。"""
    with pytest.raises(ValidationError):
        Settings(AGENT_TIMEOUT_SECONDS="abc")


def test_out_of_range_rejected():
    """越界数值（< 下限）必须被拦下。"""
    with pytest.raises(ValidationError):
        Settings(AGENT_TIMEOUT_SECONDS=0)  # ge=1
    with pytest.raises(ValidationError):
        Settings(RESEARCH_CACHE_TTL_SECONDS=-1)  # ge=0 的下界之下
    with pytest.raises(ValidationError):
        Settings(RESEARCH_CACHE_MAXSIZE=0)  # ge=1


def test_fail_fast_on_import_with_bad_env(monkeypatch):
    """环境里存在非法配置时，import app.config 必须直接失败（fail-fast 启动保护）。"""
    monkeypatch.setenv("AGENT_TIMEOUT_SECONDS", "not-a-number")
    import app.config as cfg

    with pytest.raises(RuntimeError):
        importlib.reload(cfg)
