"""运行时配置存储（前端设置界面的后端支撑）。

- 进程启动时从环境变量（由 main.py 的 _load_env_file 读 .env）初始化默认值。
- 提供运行时可变的内存字典 CONFIG，Agent / 工具调用方在**调用时**读取它，
  因此前端改配置无需重启即可生效。
- 敏感字段（API Key）在 GET 时脱敏；PUT 时写回 .env 持久化（保留其它手写行）。
- update() 同时写入 os.environ，保证直接读 os.getenv 的后端（如 WisArt）也即时生效。
"""
from __future__ import annotations

import os
from pathlib import Path

# (变量名, 默认值, 分组)。分组用于前端分区渲染与切换。
_CONFIG_SPEC: list[tuple[str, str, str]] = [
    # 文本 AI —— Agnes
    ("AGNES_API_KEY", "", "text"),
    ("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1", "text"),
    ("AGNES_TEXT_MODEL", "agnes-gpt-4o", "text"),
    ("AGNES_IMAGE_MODEL", "agnes-sd", "text"),
    ("AGNES_TIMEOUT", "60", "text"),
    # 图像生成 —— WisArt
    ("TOOL_BACKEND_IMAGE_GENERATION", "mock", "image"),
    ("WISART_API_KEY", "", "image"),
    ("WISART_BASE_URL", "https://wisart.kuaileshifu.com", "image"),
    ("WISART_ENDPOINT", "/v1/images/generations", "image"),
    ("WISART_MODEL", "gpt-image-2", "image"),
    ("WISART_AUTH_SCHEME", "Bearer", "image"),
    ("WISART_ASYNC", "0", "image"),
    ("WISART_TIMEOUT", "120", "image"),  # 单次生图请求超时（秒）
    # 其它工具后端（可选切换 mock/mcp/api）
    ("TOOL_BACKEND_AMAZON_RESEARCH", "mock", "tools"),
    ("TOOL_BACKEND_VOC_ANALYSIS", "mock", "tools"),
    ("TOOL_BACKEND_MARKET_SEARCH", "mock", "tools"),
    # 统一数据层 —— Connector 凭证与模式
    ("CONNECTOR_MODE", "auto", "connectors"),  # auto=有凭证走live否则fixture / live / fixture
    ("AMAZON_CONNECTOR_API_KEY", "", "connectors"),
    ("AMAZON_CONNECTOR_ENDPOINT", "", "connectors"),
    ("REVIEW_CONNECTOR_API_KEY", "", "connectors"),
    ("KEYWORD_CONNECTOR_API_KEY", "", "connectors"),
    ("ADS_CONNECTOR_API_KEY", "", "connectors"),
    ("IMAGE_CONNECTOR_API_KEY", "", "connectors"),
    ("IMAGE_CONNECTOR_ENDPOINT", "", "connectors"),
    # 外部数据获取工具层 —— Bright Data MCP
    ("BRIGHTDATA_API_KEY", "", "mcp"),
    ("BRIGHTDATA_ENDPOINT", "https://mcp.brightdata.com/mcp", "mcp"),
    # 服务端安全 —— 设置写入保护令牌（可选；留空则本地单用户开放）
    ("SETTINGS_API_TOKEN", "", "security"),
]

# security 分组仅用于 PUT 接受该键，绝不通过 GET /api/settings 回显（含脱敏）
_HIDDEN_GROUPS = {"security"}

_SECRETS = {"AGNES_API_KEY", "WISART_API_KEY", "AMAZON_CONNECTOR_API_KEY",
            "REVIEW_CONNECTOR_API_KEY", "KEYWORD_CONNECTOR_API_KEY",
            "ADS_CONNECTOR_API_KEY", "IMAGE_CONNECTOR_API_KEY",
            "BRIGHTDATA_API_KEY"}

# Connector 名 → 配置前缀映射
_CONNECTOR_PREFIX = {
    "amazon": "AMAZON_CONNECTOR",
    "review": "REVIEW_CONNECTOR",
    "keyword": "KEYWORD_CONNECTOR",
    "ads": "ADS_CONNECTOR",
    "image": "IMAGE_CONNECTOR",
}


def requires_settings_token() -> bool:
    """是否已启用设置写入保护令牌。

    仅在 SETTINGS_API_TOKEN 非空时返回 True——此时 PUT /api/settings 与
    POST /api/settings/test 必须携带正确令牌，否则 401。留空（默认）保持本地
    单用户开放，向后兼容。
    """
    return bool(get("SETTINGS_API_TOKEN"))


def get_connector_config(name: str) -> dict:
    """返回某 Connector 的运行配置（mode / api_key / endpoint）。"""
    prefix = _CONNECTOR_PREFIX.get(name, name.upper() + "_CONNECTOR")
    return {
        "mode": get("CONNECTOR_MODE", "auto"),
        "api_key": get(prefix + "_API_KEY", ""),
        "endpoint": get(prefix + "_ENDPOINT", ""),
    }

CONFIG: dict[str, str] = {k: os.getenv(k, default) for k, default, _ in _CONFIG_SPEC}

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/app -> 项目根
_ENV_PATH = _PROJECT_ROOT / ".env"


def get(key: str, default: str = "") -> str:
    """调用时读取（内存优先，回退到环境变量）。"""
    if key in CONFIG:
        return CONFIG[key]
    return os.getenv(key, default)


def get_all() -> dict[str, str]:
    return dict(CONFIG)


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + "•" * (len(value) - 8) + value[-4:]


def grouped() -> dict[str, dict[str, str]]:
    """按分组返回配置；密钥脱敏。security 分组（含设置令牌）不回显。"""
    groups: dict[str, dict[str, str]] = {"text": {}, "image": {}, "tools": {}, "connectors": {}, "mcp": {}}
    for k, _, group in _CONFIG_SPEC:
        if group in _HIDDEN_GROUPS:
            continue  # 安全敏感配置不通过 GET 暴露
        v = CONFIG.get(k, "")
        groups[group][k] = mask(v) if k in _SECRETS else v
    groups["text"]["__hasKey"] = bool(CONFIG.get("AGNES_API_KEY"))
    groups["image"]["__hasKey"] = bool(CONFIG.get("WISART_API_KEY"))
    groups["mcp"]["__hasKey"] = bool(CONFIG.get("BRIGHTDATA_API_KEY"))
    groups["mcp"]["__endpoint"] = CONFIG.get("BRIGHTDATA_ENDPOINT", "")
    groups["connectors"]["__hasKey"] = any(
        CONFIG.get(p + "_API_KEY") for p in _CONNECTOR_PREFIX.values()
    )
    groups["connectors"]["__mode"] = CONFIG.get("CONNECTOR_MODE", "auto")
    return groups


def update(changes: dict) -> None:
    """合并前端提交的变更（仅接受 _CONFIG_SPEC 内的键），即时生效并持久化。"""
    known = {k for k, _, _ in _CONFIG_SPEC}
    for k, v in (changes or {}).items():
        if k not in known:
            continue
        val = "" if v is None else str(v)
        CONFIG[k] = val
        os.environ[k] = val  # 让直接读 os.getenv 的后端也即时生效
    _persist()


def _persist() -> None:
    """把 _CONFIG_SPEC 涉及的键写回 .env，保留其它手写行。"""
    lines: list[str] = []
    index: dict[str, int] = {}
    if _ENV_PATH.exists():
        for raw in open(_ENV_PATH, encoding="utf-8"):
            lines.append(raw.rstrip("\n"))
            if "=" in raw and not raw.strip().startswith("#"):
                index.setdefault(raw.split("=", 1)[0].strip(), len(lines) - 1)
    for k, _, _ in _CONFIG_SPEC:
        val = CONFIG.get(k, "")
        if k in index:
            lines[index[k]] = f"{k}={val}"
        else:
            lines.append(f"{k}={val}")
    tmp = _ENV_PATH.with_suffix(".env.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    tmp.replace(_ENV_PATH)
