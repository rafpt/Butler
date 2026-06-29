"""Runtime configuration with safe, local-first defaults."""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _default_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "Butler"


def _default_scanner_outbox() -> Path:
    return Path.home() / "Library" / "Application Support" / "Data Breach Scanner" / "outbox"


def _keychain_value(service: str, account: str) -> str:
    if platform.system() != "Darwin":
        return ""
    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                service,
                "-a",
                account,
                "-w",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "development"
    log_level: str = "INFO"
    autonomy_level: int = 2
    data_dir: Path = _default_data_dir()
    timezone: str = "Europe/Lisbon"
    radar_hour: int = 7
    radar_minute: int = 30
    omlx_base_url: str = "http://127.0.0.1:8000/v1"
    omlx_model: str = "Qwen3.5-9B-OptiQ-4bit"
    omlx_api_key: str = ""
    cloud_base_url: str = ""
    cloud_model: str = ""
    cloud_api_key: str = ""
    securitywork_root: Path = Path("/Users/raf/SecurityWork")
    source_timeout_seconds: float = 15.0
    source_max_bytes: int = 2 * 1024 * 1024
    content_retention_days: int = 30
    report_retention_days: int = 365
    telegram_bot_username: str = "butleradelaidebot"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_timeout_seconds: float = 10.0
    scanner_outbox_root: Path = _default_scanner_outbox()

    @property
    def database_path(self) -> Path:
        return self.data_dir / "butler.db"

    @property
    def radar_reports_dir(self) -> Path:
        return self.data_dir / "reports" / "radar"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @classmethod
    def from_env(cls) -> Settings:
        autonomy_level = int(os.getenv("BUTLER_AUTONOMY_LEVEL", "2"))
        if autonomy_level not in range(1, 5):
            raise ValueError("BUTLER_AUTONOMY_LEVEL must be between 1 and 4")
        radar_hour = int(os.getenv("BUTLER_RADAR_HOUR", "7"))
        radar_minute = int(os.getenv("BUTLER_RADAR_MINUTE", "30"))
        if radar_hour not in range(24) or radar_minute not in range(60):
            raise ValueError("BUTLER_RADAR_HOUR/MINUTE contain an invalid time")
        return cls(
            environment=os.getenv("BUTLER_ENV", "development"),
            log_level=os.getenv("BUTLER_LOG_LEVEL", "INFO").upper(),
            autonomy_level=autonomy_level,
            data_dir=Path(os.getenv("BUTLER_DATA_DIR", str(_default_data_dir()))).expanduser(),
            timezone=os.getenv("BUTLER_TIMEZONE", "Europe/Lisbon"),
            radar_hour=radar_hour,
            radar_minute=radar_minute,
            omlx_base_url=os.getenv("BUTLER_OMLX_BASE_URL", "http://127.0.0.1:8000/v1").rstrip("/"),
            omlx_model=os.getenv("BUTLER_OMLX_MODEL", "Qwen3.5-9B-OptiQ-4bit"),
            omlx_api_key=os.getenv("BUTLER_OMLX_API_KEY", ""),
            cloud_base_url=os.getenv("BUTLER_CLOUD_BASE_URL", "").rstrip("/"),
            cloud_model=os.getenv("BUTLER_CLOUD_MODEL", ""),
            cloud_api_key=os.getenv("BUTLER_CLOUD_API_KEY", ""),
            securitywork_root=Path(
                os.getenv("BUTLER_SECURITYWORK_ROOT", "/Users/raf/SecurityWork")
            ).expanduser(),
            source_timeout_seconds=float(os.getenv("BUTLER_SOURCE_TIMEOUT_SECONDS", "15")),
            source_max_bytes=int(os.getenv("BUTLER_SOURCE_MAX_BYTES", str(2 * 1024 * 1024))),
            content_retention_days=int(os.getenv("BUTLER_CONTENT_RETENTION_DAYS", "30")),
            report_retention_days=int(os.getenv("BUTLER_REPORT_RETENTION_DAYS", "365")),
            telegram_bot_username=os.getenv(
                "BUTLER_TELEGRAM_BOT_USERNAME", "butleradelaidebot"
            ).removeprefix("@"),
            telegram_bot_token=os.getenv("BUTLER_TELEGRAM_BOT_TOKEN")
            or _keychain_value("com.butler.telegram", "bot-token"),
            telegram_chat_id=os.getenv("BUTLER_TELEGRAM_CHAT_ID")
            or _keychain_value("com.butler.telegram", "chat-id"),
            telegram_timeout_seconds=float(os.getenv("BUTLER_TELEGRAM_TIMEOUT_SECONDS", "10")),
            scanner_outbox_root=Path(
                os.getenv("BUTLER_SCANNER_OUTBOX_ROOT", str(_default_scanner_outbox()))
            ).expanduser(),
        )
