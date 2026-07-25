"""Shared async Redis client.

Redis is used for:
  - Caching published rates for fast bot reads (avoids hitting Postgres on
    every user tap).
  - Caching the daily AI summary (generated once, served to everyone).
  - Lightweight distributed locks / dedup for the scheduler.

Key naming convention (see docs/ARCHITECTURE.md for the full list):
    rate:{asset_code}              -> JSON of the latest PublishedRate
    summary:daily:{YYYY-MM-DD}     -> cached AI daily summary text
    lock:scrape:{asset_code}       -> short-lived lock to prevent overlap
"""

from __future__ import annotations

import redis.asyncio as redis

from core.config import settings
from core.logging import get_logger

log = get_logger(__name__)

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return the process-wide Redis client, creating it on first use."""
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=30,
        )
        log.info("redis_client_created")
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def check_redis_connection() -> bool:
    """Lightweight health check used by /health endpoints and monitoring."""
    try:
        client = get_redis()
        return bool(await client.ping())
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        log.error("redis_health_check_failed", error=str(exc))
        return False


# --- Cache key helpers -------------------------------------------------------
# Centralizing key formats here avoids subtle bugs where the bot and worker
# construct slightly different key strings for the same logical value.


def rate_cache_key(asset_code: str) -> str:
    return f"rate:{asset_code}"


def summary_cache_key(date_str: str) -> str:
    return f"summary:daily:{date_str}"


def scrape_lock_key(asset_code: str) -> str:
    return f"lock:scrape:{asset_code}"
