"""Central logging configuration with bounded UTF-8 log files."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from security_sanitizer import redact_sensitive_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_PATH = PROJECT_ROOT / "log" / "backend.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive_text(super().format(record))


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def configure_logging(
    *,
    logger: logging.Logger | None = None,
    log_path: Path | None = None,
    file_enabled: bool | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> logging.Logger:
    target = logger or logging.getLogger()
    target.setLevel(logging.INFO)
    if any(getattr(handler, "_quantvision_managed", False) for handler in target.handlers):
        return target

    formatter = RedactingFormatter(LOG_FORMAT)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console._quantvision_managed = True  # type: ignore[attr-defined]
    target.addHandler(console)

    enabled = _env_bool("LOG_FILE_ENABLED", True) if file_enabled is None else file_enabled
    if enabled:
        destination = Path(log_path or os.environ.get("LOG_FILE_PATH") or DEFAULT_LOG_PATH).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        rotating = RotatingFileHandler(
            destination,
            maxBytes=max(1024, int(max_bytes or os.environ.get("LOG_MAX_BYTES") or 10 * 1024 * 1024)),
            backupCount=max(1, int(backup_count or os.environ.get("LOG_BACKUP_COUNT") or 14)),
            encoding="utf-8",
        )
        rotating.setFormatter(formatter)
        rotating._quantvision_managed = True  # type: ignore[attr-defined]
        target.addHandler(rotating)
    return target
