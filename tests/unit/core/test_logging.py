"""Tests for industrial_ai.core.logging."""

import logging

import pytest

from industrial_ai.core.config import LogLevel
from industrial_ai.core.logging import FRAMEWORK_LOGGER, configure_logging, get_logger


def test_configure_sets_level_and_single_handler() -> None:
    configure_logging(LogLevel.DEBUG)
    logger = configure_logging(LogLevel.WARNING)
    assert logger.name == FRAMEWORK_LOGGER
    assert logger.level == logging.WARNING
    assert len(logger.handlers) == 1


def test_log_line_contains_level_logger_and_message(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LogLevel.INFO)
    get_logger("synthetic.engine").info("generated dataset_id=%s", "d1")
    line = capsys.readouterr().err.strip()
    assert "INFO industrial_ai.synthetic.engine generated dataset_id=d1" in line


def test_host_root_logger_is_untouched() -> None:
    root_handlers = list(logging.getLogger().handlers)
    configure_logging()
    assert logging.getLogger().handlers == root_handlers
