"""Publisher — persists a ReconciliationResult as a PublishedRate, updates
the RawReading rows it was derived from, and triggers downstream effects
(alert checks, cache invalidation).

Kept separate from `engine.py` so the reconciliation *decision* stays pure
and unit-testable while all I/O (DB writes, Redis cache updates, alert
dispatch) lives here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import AssetCategory, PublicationStatus, ReadingStatus
from core.logging import get_logger
from core.models import Asset, PublishedRate, RawReading
from core.redis_client import get_redis, rate_cache_key
from core.time import now_utc
from reconciliation.engine import ReconciliationResult

log = get_logger(__name__)

# Categories where the primary quoted unit is per-mithqal and a per-gram
# figure must also be derived and published (see product spec: gold/silver
# must show both price per mithqal and price per gram).
_METAL_CATEGORIES = {AssetCategory.GOLD, AssetCategory.SILVER}


async def publish_reconciliation_result(
    session: AsyncSession,
    asset: Asset,
    result: ReconciliationResult,
    *,
    mithqal_grams: float,
) -> PublishedRate:
    """Persist one reconciliation outcome for one asset.

    Always writes a `PublishedRate` row — even when the result is
    `PENDING_REVIEW` — so admins have a concrete record to approve/reject
    (see bot/handlers/admin.py). Only `PUBLISHED` rows are ever shown to
    regular users or read by the AI summary (enforced in history/rates.py
    and the AI reader, not just here — defense in depth).
    """
    price_per_gram = None
    if result.price is not None and asset.category in _METAL_CATEGORIES and mithqal_grams > 0:
        price_per_gram = result.price / mithqal_grams

    daily_change_pct, daily_change_abs = await _compute_daily_change(
        session, asset.id, result.price
    )

    published_rate = PublishedRate(
        asset_id=asset.id,
        price=result.price if result.price is not None else 0,
        price_per_gram=price_per_gram,
        daily_change_pct=daily_change_pct,
        daily_change_abs=daily_change_abs,
        effective_at=now_utc(),
        status=result.status,
        confidence_score=result.confidence_score,
        source_reading_ids=result.used_reading_ids,
        review_reason=result.review_reason,
        reconciliation_meta=result.meta,
    )
    session.add(published_rate)

    await _mark_readings(session, result)

    await session.flush()  # populate published_rate.id before caching

    if result.status == PublicationStatus.PUBLISHED:
        await _update_cache(asset.code, published_rate)
        log.info(
            "rate_published",
            asset=asset.code,
            price=float(published_rate.price),
            confidence=published_rate.confidence_score,
        )
    else:
        log.warning(
            "rate_flagged_for_review",
            asset=asset.code,
            reason=result.review_reason,
        )

    return published_rate


async def resolve_admin_review(
    session: AsyncSession,
    rate: PublishedRate,
    *,
    approve: bool,
    admin_telegram_id: int,
) -> PublishedRate:
    """Apply an admin's approve/reject decision to a PENDING_REVIEW rate.

    Approving sets status to PUBLISHED (making it visible to users and the
    AI summary immediately) and refreshes the Redis cache exactly like an
    automatic publication would — from the bot/AI's perspective there is
    no difference between an auto-published rate and an admin-approved
    one, only the audit trail (`reviewed_by_admin_id`/`reviewed_at`)
    differs.
    """
    rate.reviewed_by_admin_id = admin_telegram_id
    rate.reviewed_at = now_utc()

    if approve:
        rate.status = PublicationStatus.PUBLISHED
        asset = await session.get(Asset, rate.asset_id)
        if asset is not None:
            await _update_cache(asset.code, rate)
        log.info("rate_review_approved", rate_id=str(rate.id), admin=admin_telegram_id)
    else:
        rate.status = PublicationStatus.REJECTED
        log.info("rate_review_rejected", rate_id=str(rate.id), admin=admin_telegram_id)

    return rate


async def _mark_readings(session: AsyncSession, result: ReconciliationResult) -> None:
    used_ids = set(result.used_reading_ids)
    rejected_ids = set(result.rejected_reading_ids)
    all_ids = used_ids | rejected_ids
    if not all_ids:
        return

    rows = (
        await session.execute(select(RawReading).where(RawReading.id.in_(all_ids)))
    ).scalars()

    for reading in rows:
        if reading.id in used_ids:
            reading.status = ReadingStatus.RECONCILED
        elif reading.id in rejected_ids:
            reading.status = ReadingStatus.REJECTED
            reading.rejection_reason = result.rejection_reasons.get(reading.id)


async def _compute_daily_change(
    session: AsyncSession, asset_id: uuid.UUID, new_price: float | None
) -> tuple[float | None, float | None]:
    """Percent/absolute change vs. the most recent PUBLISHED rate (before
    this one) for the same asset. Returns (None, None) if there's no prior
    published rate or the new value couldn't be computed."""
    if new_price is None:
        return None, None

    previous = (
        await session.execute(
            select(PublishedRate)
            .where(
                PublishedRate.asset_id == asset_id,
                PublishedRate.status == PublicationStatus.PUBLISHED,
            )
            .order_by(PublishedRate.effective_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if previous is None or not previous.price:
        return None, None

    previous_price = float(previous.price)
    abs_change = new_price - previous_price
    pct_change = (abs_change / previous_price) * 100
    return round(pct_change, 4), round(abs_change, 6)


async def _update_cache(asset_code: str, rate: PublishedRate) -> None:
    """Refresh the Redis cache the bot reads from, so users see the new
    price immediately without waiting on Postgres replication lag or the
    bot's own query."""
    import orjson

    redis = get_redis()
    payload = {
        "price": float(rate.price),
        "price_per_gram": float(rate.price_per_gram) if rate.price_per_gram is not None else None,
        "daily_change_pct": float(rate.daily_change_pct) if rate.daily_change_pct is not None else None,
        "daily_change_abs": float(rate.daily_change_abs) if rate.daily_change_abs is not None else None,
        "effective_at": rate.effective_at.isoformat(),
        "confidence_score": rate.confidence_score,
    }
    await redis.set(rate_cache_key(asset_code), orjson.dumps(payload).decode(), ex=3600)
