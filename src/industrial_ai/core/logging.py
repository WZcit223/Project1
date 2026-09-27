"""Logging setup for framework processes (stdlib ``logging``, one consistent line format)."""

import logging

from industrial_ai.core.config import LogLevel

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
FRAMEWORK_LOGGER = "industrial_ai"


def configure_logging(level: LogLevel = LogLevel.INFO) -> logging.Logger:
    """Configure the ``industrial_ai`` logger hierarchy and return its root logger.

    Idempotent: calling it again replaces the handler instead of adding a duplicate.
    Only the framework logger is configured; the root logger of the host process is untouched.
    """
    logger = logging.getLogger(FRAMEWORK_LOGGER)
    logger.setLevel(level.value)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    """Logger inside the framework hierarchy, e.g. ``get_logger("synthetic.engine")``."""
    return logging.getLogger(f"{FRAMEWORK_LOGGER}.{name}")
