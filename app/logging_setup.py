"""Logging configuration module for BugSleuth."""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


class JsonLogFormatter(logging.Formatter):
    """Format log records as single-line structured JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging(
    log_level: int = logging.INFO,
    log_file: str | Path | None = None,
    json_format: bool = False,
) -> logging.Logger:
    """Configure structured logging for BugSleuth.

    Args:
        log_level: Logging severity level (e.g., logging.INFO, logging.DEBUG).
        log_file: Optional path to a file where logs should be appended.
        json_format: Whether to output logs in structured JSON format.

    Returns:
        The configured root logger for bugsleuth.
    """
    logger = logging.getLogger("bugsleuth")
    if logger.handlers:
        return logger

    logger.setLevel(log_level)

    # Check environment variable for JSON logging override
    use_json = json_format or os.getenv("LOG_FORMAT", "").lower() == "json"

    if use_json:
        formatter = JsonLogFormatter()
    else:
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
