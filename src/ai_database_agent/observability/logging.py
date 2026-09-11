"""
Detailed, file-based application logging.

This is separate from tracing.py (spans/traces for the pipeline's
internal flow). This module is for *debugging real failures on a
user's machine*: every request, LLM call, SQL attempt, and exception
gets a timestamped, leveled line written to a rotating log file on
disk, with full tracebacks -- not just "something went wrong".

Usage:
    from ai_database_agent.observability.logging import setup_logging, get_logger

    setup_logging()  # call once, e.g. at app/CLI startup
    log = get_logger(__name__)

    log.info("ask.start", extra={"session_id": session_id, "question": question})
    log.exception("ask.failed")  # captures the full traceback automatically

Log files are written to LOG_DIR (default: "./logs") as:
    logs/app.log          - everything at LOG_LEVEL and above, rotated at 5MB x 5 backups
    logs/errors.log       - WARNING and above only, kept separately so
                            real problems aren't buried in routine INFO lines

Both files use a verbose formatter (timestamp, level, logger name,
module:line, message) so a stack trace can be traced back to the
exact line without needing to reproduce the bug interactively.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from ai_database_agent.config import get_settings

_INITIALIZED = False

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(module)s:%(lineno)d | %(message)s"
)


def setup_logging(log_dir: str | Path = "logs") -> None:
    """Configure the root logger exactly once per process.

    Adds three handlers:
      - console: LOG_LEVEL and above, for the terminal the app is
        running in (short-term feedback while developing).
      - logs/app.log: LOG_LEVEL and above, rotating, for full history.
      - logs/errors.log: WARNING and above only, rotating, so errors
        are easy to find without scrolling through routine request logs.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    app_handler = logging.handlers.RotatingFileHandler(
        log_path / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    app_handler.setLevel(level)
    app_handler.setFormatter(formatter)

    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "errors.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)

    # Third-party libraries (uvicorn, httpx, sqlalchemy) are noisy at
    # DEBUG/INFO; keep them at WARNING unless the app itself is set to
    # DEBUG, in which case let everything through for deep debugging.
    if level > logging.DEBUG:
        for noisy in ("httpx", "httpcore", "sqlalchemy.engine", "uvicorn.access"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    _INITIALIZED = True
    get_logger(__name__).info(
        "logging.initialized",
        extra={"log_dir": str(log_path.resolve()), "level": settings.log_level},
    )


def get_logger(name: str) -> logging.Logger:
    """Return a logger for `name` (typically __name__ of the calling module)."""
    if not _INITIALIZED:
        setup_logging()
    return logging.getLogger(name)
