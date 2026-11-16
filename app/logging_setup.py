"""Logging configuration module for BugSleuth."""

import logging
import os
import sys
from pathlib import Path


def setup_logging(
    log_level: int = logging.INFO,
    log_file: str | Path | None = None,
) -> logging.Logger:
    """Configure structured logging for BugSleuth.

    Args:
        log_level: Logging severity level (e.g., logging.INFO, logging.DEBUG).
        log_file: Optional path to a file where logs should be appended.

    Returns:
        The configured root logger for bugsleuth.
    """
    logger = logging.getLogger("bugsleuth")
    if logger.handlers:
        # Already configured
        return logger

    logger.setLevel(log_level)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler if specified or default data/bugsleuth.log
    if log_file is None:
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        log_file = data_dir / "bugsleuth.log"
    else:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Retrieve a child logger under the bugsleuth namespace.

    Args:
        name: Name of the child module or component.

    Returns:
        A child logger instance.
    """
    return logging.getLogger(f"bugsleuth.{name}")
