"""
KnowledgeFlow — Structured Logging Configuration

Uses structlog for structured JSON logging in production
and colorized human-readable output in development (LOG_LEVEL=DEBUG).

Usage:
    from utils.logging_config import configure_logging
    configure_logging(level="INFO")

    import structlog
    log = structlog.get_logger(__name__)
    log.info("event.name", key="value", count=42)
"""
from __future__ import annotations

import io
import logging
import sys
from typing import Any

# Force UTF-8 encoding on standard output to prevent Windows charmap crashes
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding='utf-8')


def configure_logging(level: str = "INFO") -> None:
    """
    Configure structlog for the application.

    In DEBUG mode  → colorized, human-readable console output.
    In other modes → JSON output suitable for log aggregation.
    """
    import structlog

    log_level = getattr(logging, level.upper(), logging.INFO)
    is_dev = level.upper() == "DEBUG"

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]

    if is_dev:
        # Pretty colored output for development
        renderer: Any = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Machine-readable JSON for production
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also silence noisy third-party loggers
    for noisy_lib in ("httpx", "httpcore", "telegram", "hpack"):
        logging.getLogger(noisy_lib).setLevel(logging.WARNING)

    # Stdlib logging → structlog bridge (for third-party libs)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
