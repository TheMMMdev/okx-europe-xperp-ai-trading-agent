"""Central source of truth for Quant Agent EU version and branding.

Public distribution metadata is intentionally blank until the operator configures
`ASTRA_APP_SITE` / `ASTRA_APP_REPO`; the historical `ASTRA_*` internal namespace is
kept for compatibility with data stores and configuration keys.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _env_value(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value.strip()
    env_path = ROOT / ".env"
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, raw = stripped.split("=", 1)
            if key.strip() == name:
                return raw.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


__version__ = "8.5.0-eu.1"
APP_VERSION = f"v{__version__}"
APP_NAME = "Quant Agent EU"
APP_NAME_EN = "Quant Agent EU"
APP_SITE = ""
APP_REPO = ""
APP_SITE = (_env_value("ASTRA_APP_SITE") or APP_SITE).rstrip("/")
APP_REPO = _env_value("ASTRA_APP_REPO") or APP_REPO


def get_version() -> str:
    """动态读取当前工作区真实声明的版本号。

    优先从磁盘文件读取最新版本；若读取失败则回退到导入期的静态 __version__。
    确保无论常驻进程是否重启，展示层与对外 API 均能即时感知本地 Git 状态与版本变更。
    """
    try:
        v_path = Path(__file__).resolve()
        content = v_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("__version__") and "=" in line:
                return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return __version__
