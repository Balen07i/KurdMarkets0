"""Async SQLAlchemy engine + session management.

Both the bot and the worker import `get_session` / `session_scope` from
here. Nothing outside `core` should construct its own engine — this keeps
connection pooling and lifecycle centralized.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import settings
from core.logging import get_logger

log = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800,
        )
        log.info("db_engine_created", url_host=_safe_host(settings.database_url))
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a transactional scope around a series of operations.

    Commits on success, rolls back on any exception, always closes.

    Usage:
        async with session_scope() as session:
            session.add(obj)
    """
    session = get_session_factory()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Cleanly close all pooled connections. Call on process shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def check_db_connection() -> bool:
    """Lightweight health check used by /health endpoints and monitoring."""
    from sqlalchemy import text

    try:
        async with session_scope() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        log.error("db_health_check_failed", error=str(exc))
        return False


def _safe_host(url: str) -> str:
    """Extract just the host from a DB URL for logging (never log credentials)."""
    try:
        return url.split("@")[-1].split("/")[0]
    except Exception:  # noqa: BLE001
        return "unknown"
