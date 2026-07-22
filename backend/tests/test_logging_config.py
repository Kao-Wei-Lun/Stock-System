import logging

from logging_config import configure_logging


def test_configure_logging_adds_one_console_and_rotating_file_handler(tmp_path):
    logger = logging.getLogger("quantvision.logging-test")
    logger.handlers.clear()
    logger.propagate = False
    log_path = tmp_path / "logs" / "backend.log"

    configure_logging(logger=logger, log_path=log_path, max_bytes=1024, backup_count=2)
    configure_logging(logger=logger, log_path=log_path, max_bytes=1024, backup_count=2)
    logger.info("health probe")
    for handler in logger.handlers:
        handler.flush()

    assert len(logger.handlers) == 2
    assert "health probe" in log_path.read_text(encoding="utf-8")
    logger.handlers.clear()
