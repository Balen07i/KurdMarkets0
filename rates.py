"""Read-only queries over verified published rate history.

This is the ONLY module the Telegram bot's handlers should import from to
display prices — handlers must never construct their own SQLAlchemy
queries against `PublishedRate` or (especially) `RawReading` directly,
both to keep the "AI/bot only reads published data" rule enforced in one
place and so caching (see `get_current_rate`) is applied consistently.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import PublicationStatus
from core.logging import get_logger
from core.models import Asset, PublishedRate
from core.redis_client import get_redis, rate_cache_key

log = get_logger(__name__)


async def get_asset_by_code(session: AsyncSession, code: str) -> Asset | None:
    return (
        await session.execute(select(Asset).where(Asset.code == code))
    ).scalar_one_or_none()


async def list_active_assets(session: AsyncSession, category: str | None = None) -> list[Asset]:
    query = select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.sort_order)
    if category is not None:
        query = query.where(Asset.category == category)
    return list((await session.execute(query)).scalars().all())


async def get_current_rate(session: AsyncSession, asset: Asset) -> PublishedRate | None:
    """Latest published rate for one asset.

    Callers needing low-latency reads (bot handlers on the hot path)
    should prefer reading straight from the Redis cache
    (`core.redis_client.rate_cache_key`) which `reconciliation.publisher`
    keeps fresh; this function is the Postgres-backed fallback/source of
    truth used when the cache is empty (e.g. right after a Redis restart)
    or for any query beyond "the single latest value".
    """
    return (
        await session.execute(
            select(PublishedRate)
            .where(
                PublishedRate.asset_id == asset.id,
                PublishedRate.status == PublicationStatus.PUBLISHED,
            )
            .order_by(PublishedRate.effective_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def get_historical_rates(
    session: AsyncSession,
    asset: Asset,
    *,
    since: datetime,
    until: datetime | None = None,
    limit: int = 500,
) -> list[PublishedRate]:
    """Published (verified only) rate history for one asset in a time
    window, most recent first. Used by the bot's "Historical data"
    feature (see bot/handlers/currencies.py)."""
    query = (
        select(PublishedRate)
        .where(
            PublishedRate.asset_id == asset.id,
            PublishedRate.status == PublicationStatus.PUBLISHED,
            PublishedRate.effective_at >= since,
        )
        .order_by(PublishedRate.effective_at.desc())
        .limit(limit)
    )
    if until is not None:
        query = query.where(PublishedRate.effective_at <= until)

    return list((await session.execute(query)).scalars().all())


async def get_all_current_rates(session: AsyncSession) -> dict[str, PublishedRate]:
    """Latest published rate for every active asset, keyed by asset code.
    Used by the AI daily summary generator, which needs a full snapshot of
    "today's market" across every category in one call."""
    assets = await list_active_assets(session)
    result: dict[str, PublishedRate] = {}
    for asset in assets:
        rate = await get_current_rate(session, asset)
        if rate is not None:
            result[asset.code] = rate
    return result
