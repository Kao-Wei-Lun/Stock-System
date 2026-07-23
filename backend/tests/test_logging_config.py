from __future__ import annotations

import logging
import os
from datetime import timedelta

from logging_config import (
    HybridRotatingFileHandler,
    configure_channel_logging,
    configure_logging,
)


def _close_handlers(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()


def test_configure_logging_adds_one_console_and_bounded_file_handler(tmp_path):
    logger = logging.getLogger("quantvision.logging-test")
    _close_handlers(logger)
    logger.propagate = False
    log_path = tmp_path / "logs" / "backend.log"

    configure_logging(
        logger=logger,
        profile="production",
        log_path=log_path,
        max_bytes=1024,
        backup_count=2,
        retention_days=2,
    )
    configure_logging(logger=logger, profile="production", log_path=log_path)
    logger.info("health probe")
    for handler in logger.handlers:
        handler.flush()

    assert len(logger.handlers) == 2
    assert any(isinstance(handler, HybridRotatingFileHandler) for handler in logger.handlers)
    assert "health probe" in log_path.read_text(encoding="utf-8")
    _close_handlers(logger)


def test_runtime_profiles_keep_test_scheduler_and_production_logs_separate(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTVISION_RUNTIME_PROFILE", "test")
    test_logger = logging.getLogger("quantvision.test-profile")
    scheduler_logger = logging.getLogger("quantvision.test-scheduler")
    _close_handlers(test_logger)
    _close_handlers(scheduler_logger)
    test_logger.propagate = False

    configure_logging(logger=test_logger, log_dir=tmp_path, console_enabled=False)
    configure_channel_logging(
        scheduler_logger.name,
        profile="scheduler",
        log_dir=tmp_path,
        console_enabled=False,
    )
    test_logger.info("test-only")
    scheduler_logger.info("scheduler-only")
    for handler in [*test_logger.handlers, *scheduler_logger.handlers]:
        handler.flush()

    assert "test-only" in (tmp_path / "test.log").read_text(encoding="utf-8")
    assert "scheduler-only" not in (tmp_path / "test.log").read_text(encoding="utf-8")
    assert "scheduler-only" in (tmp_path / "test-scheduler.log").read_text(encoding="utf-8")
    assert not (tmp_path / "backend.log").exists()
    assert not (tmp_path / "scheduler.log").exists()
    _close_handlers(test_logger)
    _close_handlers(scheduler_logger)


def test_scheduler_channel_does_not_duplicate_into_backend_log(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTVISION_RUNTIME_PROFILE", "production")
    backend_logger = logging.getLogger("quantvision.isolated-backend")
    scheduler_logger = logging.getLogger("quantvision.isolated-scheduler")
    _close_handlers(backend_logger)
    _close_handlers(scheduler_logger)
    backend_logger.propagate = False

    configure_logging(
        logger=backend_logger,
        profile="production",
        log_path=tmp_path / "backend.log",
        console_enabled=False,
    )
    configure_logging(
        logger=scheduler_logger,
        profile="scheduler",
        log_path=tmp_path / "scheduler.log",
        console_enabled=False,
        propagate=False,
    )
    backend_logger.info("backend-event")
    scheduler_logger.info("scheduler-event")
    for handler in [*backend_logger.handlers, *scheduler_logger.handlers]:
        handler.flush()

    backend_text = (tmp_path / "backend.log").read_text(encoding="utf-8")
    scheduler_text = (tmp_path / "scheduler.log").read_text(encoding="utf-8")
    assert "backend-event" in backend_text
    assert "scheduler-event" not in backend_text
    assert "scheduler-event" in scheduler_text
    _close_handlers(backend_logger)
    _close_handlers(scheduler_logger)


def test_hybrid_handler_rotates_by_date_and_prunes_old_archives(tmp_path):
    path = tmp_path / "backend.log"
    logger = logging.getLogger("quantvision.hybrid-rotation")
    _close_handlers(logger)
    logger.propagate = False
    handler = HybridRotatingFileHandler(
        path,
        max_bytes=1024,
        backup_count=3,
        retention_days=1,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.info("previous-day")
    handler.flush()
    handler._opened_date = handler._today() - timedelta(days=1)

    logger.info("new-day")
    handler.flush()
    archives = list(tmp_path.glob("backend.*.log"))

    assert len(archives) == 1
    assert "new-day" in path.read_text(encoding="utf-8")
    handler.close()
    logger.handlers.clear()

    stale = tmp_path / "backend.2000-01-01_00-00-00.log"
    stale.write_text("old", encoding="utf-8")
    old_timestamp = 946684800
    os.utime(stale, (old_timestamp, old_timestamp))
    replacement = HybridRotatingFileHandler(
        path,
        max_bytes=1024,
        backup_count=3,
        retention_days=1,
    )
    replacement.close()

    assert not stale.exists()
