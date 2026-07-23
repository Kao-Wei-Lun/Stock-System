"""Central logging with profile isolation, redaction, and bounded retention."""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timedelta
from logging.handlers import BaseRotatingHandler
from pathlib import Path
from threading import Lock

from security_sanitizer import redact_sensitive_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIR = PROJECT_ROOT / "log"
PROFILE_FILENAMES = {
    "production": "backend.log",
    "test": "test.log",
    "scheduler": "scheduler.log",
    "test-scheduler": "test-scheduler.log",
    "backup": "backup.log",
}
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive_text(super().format(record))


class HybridRotatingFileHandler(BaseRotatingHandler):
    """Rotate on local date change or size, then prune by age and count."""

    def __init__(
        self,
        filename: str | os.PathLike[str],
        *,
        max_bytes: int,
        backup_count: int,
        retention_days: int,
        encoding: str = "utf-8",
    ) -> None:
        self.max_bytes = max(1024, int(max_bytes))
        self.backup_count = max(1, int(backup_count))
        self.retention_days = max(1, int(retention_days))
        self._opened_date = self._today()
        self._rollover_lock = Lock()
        super().__init__(filename, mode="a", encoding=encoding, delay=False)
        self._prune_archives()

    @staticmethod
    def _today() -> date:
        return datetime.now().astimezone().date()

    def _archive_pattern(self) -> str:
        path = Path(self.baseFilename)
        return f"{path.stem}.*{path.suffix}"

    def shouldRollover(self, record: logging.LogRecord) -> bool:  # noqa: N802
        if self._today() != self._opened_date:
            return True
        if self.stream is None:
            self.stream = self._open()
        message = f"{self.format(record)}{self.terminator}"
        self.stream.seek(0, os.SEEK_END)
        return self.stream.tell() + len(message.encode(self.encoding or "utf-8")) >= self.max_bytes

    def doRollover(self) -> None:  # noqa: N802
        with self._rollover_lock:
            if self.stream:
                self.stream.close()
                self.stream = None
            source = Path(self.baseFilename)
            if source.is_file() and source.stat().st_size:
                timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
                destination = source.with_name(f"{source.stem}.{timestamp}{source.suffix}")
                sequence = 1
                while destination.exists():
                    destination = source.with_name(
                        f"{source.stem}.{timestamp}.{sequence}{source.suffix}"
                    )
                    sequence += 1
                os.replace(source, destination)
            self._opened_date = self._today()
            self.stream = self._open()
            self._prune_archives()

    def _prune_archives(self) -> None:
        base = Path(self.baseFilename)
        cutoff = datetime.now().astimezone() - timedelta(days=self.retention_days)
        archives = sorted(
            base.parent.glob(self._archive_pattern()),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        for index, archive in enumerate(archives):
            modified = datetime.fromtimestamp(archive.stat().st_mtime).astimezone()
            if index >= self.backup_count or modified < cutoff:
                try:
                    archive.unlink()
                except OSError:
                    continue


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def detect_runtime_profile() -> str:
    explicit = str(os.environ.get("QUANTVISION_RUNTIME_PROFILE") or "").strip().lower()
    if explicit in PROFILE_FILENAMES:
        return explicit
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return "test"
    return "production"


def _default_path(profile: str, log_dir: Path | None = None) -> Path:
    normalized = profile if profile in PROFILE_FILENAMES else "production"
    return Path(log_dir or DEFAULT_LOG_DIR) / PROFILE_FILENAMES[normalized]


def _managed_handlers(target: logging.Logger) -> list[logging.Handler]:
    return [
        handler for handler in target.handlers
        if getattr(handler, "_quantvision_managed", False)
    ]


def configure_logging(
    *,
    logger: logging.Logger | None = None,
    profile: str | None = None,
    log_path: Path | None = None,
    log_dir: Path | None = None,
    file_enabled: bool | None = None,
    console_enabled: bool = True,
    max_bytes: int | None = None,
    backup_count: int | None = None,
    retention_days: int | None = None,
    propagate: bool | None = None,
) -> logging.Logger:
    target = logger or logging.getLogger()
    if _managed_handlers(target):
        return target

    normalized_profile = str(profile or detect_runtime_profile()).strip().lower()
    if normalized_profile not in PROFILE_FILENAMES:
        raise ValueError(f"Unsupported log profile: {normalized_profile}")
    target.setLevel(logging.INFO)
    if propagate is not None:
        target.propagate = bool(propagate)

    formatter = RedactingFormatter(LOG_FORMAT)
    if console_enabled:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console._quantvision_managed = True  # type: ignore[attr-defined]
        console._quantvision_profile = normalized_profile  # type: ignore[attr-defined]
        target.addHandler(console)

    enabled = _env_bool("LOG_FILE_ENABLED", True) if file_enabled is None else file_enabled
    if enabled:
        configured_path = os.environ.get("LOG_FILE_PATH") if normalized_profile == "production" else None
        destination = Path(
            log_path
            or configured_path
            or _default_path(normalized_profile, log_dir)
        ).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        rotating = HybridRotatingFileHandler(
            destination,
            max_bytes=int(max_bytes or os.environ.get("LOG_MAX_BYTES") or 10 * 1024 * 1024),
            backup_count=int(backup_count or os.environ.get("LOG_BACKUP_COUNT") or 14),
            retention_days=int(retention_days or os.environ.get("LOG_RETENTION_DAYS") or 14),
        )
        rotating.setFormatter(formatter)
        rotating._quantvision_managed = True  # type: ignore[attr-defined]
        rotating._quantvision_profile = normalized_profile  # type: ignore[attr-defined]
        target.addHandler(rotating)
    return target


def configure_channel_logging(
    logger_name: str,
    *,
    profile: str,
    log_dir: Path | None = None,
    console_enabled: bool = True,
) -> logging.Logger:
    """Configure a non-propagating channel so its records do not enter backend.log."""

    effective_profile = profile
    if detect_runtime_profile() == "test" and profile == "scheduler":
        effective_profile = "test-scheduler"
    return configure_logging(
        logger=logging.getLogger(logger_name),
        profile=effective_profile,
        log_dir=log_dir,
        console_enabled=console_enabled,
        propagate=False,
    )
