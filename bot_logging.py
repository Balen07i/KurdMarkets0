"""Structured logging configuration shared by the bot and worker processes.

Uses `structlog` on top of the standard library `logging` module so logs are
emitted as single-line JSON in production (easy to query in Railway's log
viewer or any log aggregator) and as readable colored text in development.
"""

from __future__ import annotations

import logging
import sys

import structlog

from core.config import settings


def configure_logging() -> None:
    """Configure stdlib logging + structlog. Call once at process startup."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structlog logger.

    Usage:
        log = get_logger(__name__)
        log.info("rate_published", asset="usd_iqd_official", price=1310.5)
    """
    return structlog.get_logger(name)
