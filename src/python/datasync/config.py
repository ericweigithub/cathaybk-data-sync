"""
設定管理
支援從 config.yaml 讀取結構設定，API Key 透過環境變數注入。

載入順序：
1. 讀取 config.yaml（或由 CONFIG_PATH 環境變數指定路徑）
2. API Key 值若為 "${ENV_VAR}" 格式，自動從環境變數展開
3. 可直接以環境變數覆蓋 (CLOUDABILITY_BASE_URL, FCOE_API_KEY 等)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

_ENV_PLACEHOLDER_RE = re.compile(r"^\$\{(.+)\}$")

# ---------------------------------------------------------------------------
# 設定資料類別
# ---------------------------------------------------------------------------


@dataclass
class EnvironmentConfig:
    """單一 Cloudability 環境設定（子公司或 FCoE）"""

    name: str
    api_key: str


@dataclass
class HttpConfig:
    """HTTP Client 設定"""

    connect_timeout_seconds: int = 30
    read_timeout_seconds: int = 60
    max_retry: int = 3
    retry_interval_seconds: int = 60


@dataclass
class CloudabilityConfig:
    """Cloudability 全域設定"""

    base_url: str = "https://api.cloudability.com/v3"
    subsidiaries: list[EnvironmentConfig] = field(default_factory=list)
    fcoe: EnvironmentConfig = field(
        default_factory=lambda: EnvironmentConfig(name="FCoE", api_key="")
    )
    http: HttpConfig = field(default_factory=HttpConfig)


@dataclass
class SyncConfig:
    """同步作業設定"""

    vendors: list[str] = field(default_factory=lambda: ["amazon", "google"])
    enable_delete: bool = False
    cron: str = "0 2 * * *"          # 每日凌晨 02:00（Unix cron 格式）
    schedule_enabled: bool = True
    log_path: str = "./logs/sync.log"


@dataclass
class AppConfig:
    """應用程式完整設定"""

    cloudability: CloudabilityConfig = field(default_factory=CloudabilityConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)


# ---------------------------------------------------------------------------
# 內部工具函式
# ---------------------------------------------------------------------------


def _expand_env(value: str) -> str:
    """若 value 為 ${ENV_VAR} 格式，從環境變數取值；否則原值回傳"""
    match = _ENV_PLACEHOLDER_RE.match(value)
    if match:
        env_var = match.group(1)
        resolved = os.environ.get(env_var, "")
        if not resolved:
            import warnings
            warnings.warn(
                f"環境變數 {env_var} 未設定，對應 API Key 將為空字串", stacklevel=3
            )
        return resolved
    return value


def _parse_environment_config(raw: dict) -> EnvironmentConfig:
    return EnvironmentConfig(
        name=raw.get("name", ""),
        api_key=_expand_env(str(raw.get("api_key", raw.get("api-key", "")))),
    )


def _parse_http_config(raw: dict) -> HttpConfig:
    return HttpConfig(
        connect_timeout_seconds=int(
            raw.get("connect_timeout_seconds", raw.get("connect-timeout-seconds", 30))
        ),
        read_timeout_seconds=int(
            raw.get("read_timeout_seconds", raw.get("read-timeout-seconds", 60))
        ),
        max_retry=int(raw.get("max_retry", raw.get("max-retry", 3))),
        retry_interval_seconds=int(
            raw.get("retry_interval_seconds", raw.get("retry-interval-seconds", 60))
        ),
    )


def _parse_cloudability_config(raw: dict) -> CloudabilityConfig:
    base_url = os.environ.get(
        "CLOUDABILITY_BASE_URL",
        raw.get("base_url", raw.get("base-url", "https://api.cloudability.com/v3")),
    )

    subsidiaries = [
        _parse_environment_config(s) for s in raw.get("subsidiaries", [])
    ]

    fcoe_raw = raw.get("fcoe", {})
    fcoe = _parse_environment_config(fcoe_raw) if fcoe_raw else CloudabilityConfig().fcoe

    http_raw = raw.get("http", {})
    http_cfg = _parse_http_config(http_raw) if http_raw else HttpConfig()

    return CloudabilityConfig(
        base_url=base_url,
        subsidiaries=subsidiaries,
        fcoe=fcoe,
        http=http_cfg,
    )


def _parse_sync_config(raw: dict) -> SyncConfig:
    return SyncConfig(
        vendors=raw.get("vendors", ["amazon", "google"]),
        enable_delete=bool(raw.get("enable_delete", raw.get("enable-delete", False))),
        cron=raw.get("cron", "0 2 * * *"),
        schedule_enabled=bool(
            raw.get("schedule_enabled", raw.get("schedule-enabled", True))
        ),
        log_path=raw.get("log_path", raw.get("log-path", "./logs/sync.log")),
    )


# ---------------------------------------------------------------------------
# 公開進入點
# ---------------------------------------------------------------------------


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """
    載入應用程式設定。

    Args:
        config_path: config.yaml 路徑；若為 None，依序嘗試：
                     1. 環境變數 CONFIG_PATH
                     2. ./config.yaml
                     3. 使用預設值

    Returns:
        AppConfig 實例
    """
    if config_path is None:
        env_path = os.environ.get("CONFIG_PATH")
        if env_path:
            config_path = Path(env_path)
        else:
            config_path = Path("config.yaml")

    config_path = Path(config_path)

    if not config_path.exists():
        return AppConfig()

    _yaml = YAML()
    _yaml.preserve_quotes = True
    with config_path.open("r", encoding="utf-8") as fh:
        raw = dict(_yaml.load(fh) or {})

    cloudability_raw = raw.get("cloudability", raw.get("environments", {}))
    # 相容規格書的 environments.subsidiaries / environments.fcoe 格式
    if "subsidiaries" not in cloudability_raw and "subsidiaries" in raw.get("environments", {}):
        cloudability_raw = raw["environments"]

    return AppConfig(
        cloudability=_parse_cloudability_config(cloudability_raw),
        sync=_parse_sync_config(raw.get("sync", {})),
    )
