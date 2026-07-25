"""Health checks run periodically by the worker (see worker/jobs/health.py):
stale published data and degraded/failing sources.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.enums import PublicationStatus, SourceStatus
from core.logging import get_logger
from core.models import Asset, PublishedRate, Source
from core.time import minutes_since

log = get_logger(__name__)

# A source is considered "degraded" (worth an admin alert, but not yet
# disabled) after this many consecutive failures.
DEGRADED_FAILURE_THRESHOLD = 3
# A source is automatically disabled (excluded from reconciliation until
# an admin re-enables it) after this many consecutive failures — this is
# the "a source changes [format/availability]" case from the spec.
DISABLE_FAILURE_THRESHOLD = 10


@dataclass(frozen=True, slots=True)
class StaleAsset:
    asset_code: str
    asset_name_en: str
    minutes_since_update: float


@dataclass(frozen=True, slots=True)
class UnhealthySource:
    source_name: str
    asset_code: str
    consecutive_failures: int
    last_error: str | None


async def find_stale_assets(session: AsyncSession) -> list[StaleAsset]:
    """Every active asset whose latest PUBLISHED rate is older than
    `settings.stale_threshold_minutes`, or that has never published at
    all."""
    stale: list[StaleAsset] = []

    assets = (
        await session.execute(select(Asset).where(Asset.is_active.is_(True)))
    ).scalars().all()

    for asset in assets:
        latest = (
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

        if latest is None:
            stale.append(StaleAsset(asset.code, asset.name_en, minutes_since_update=float("inf")))
            continue

        age = minutes_since(latest.effective_at)
        if age > settings.stale_threshold_minutes:
            stale.append(StaleAsset(asset.code, asset.name_en, minutes_since_update=age))

    return stale


async def find_unhealthy_sources(session: AsyncSession) -> list[UnhealthySource]:
    """Every ACTIVE source with enough consecutive failures to warrant an
    admin alert (does not include already-DISABLED sources — those have
    already been alerted on and acted upon)."""
    sources = (
        await session.execute(
            select(Source).where(
                Source.status.in_([SourceStatus.ACTIVE, SourceStatus.DEGRADED]),
                Source.consecutive_failures >= DEGRADED_FAILURE_THRESHOLD,
            )
        )
    ).scalars().all()

    unhealthy: list[UnhealthySource] = []
    for source in sources:
        asset = await session.get(Asset, source.asset_id)
        unhealthy.append(
            UnhealthySource(
                source_name=source.name,
                asset_code=asset.code if asset else "unknown",
                consecutive_failures=source.consecutive_failures,
                last_error=source.last_error,
            )
        )
    return unhealthy


async def apply_source_status_transitions(session: AsyncSession) -> list[Source]:
    """Promote sources through active -> degraded -> disabled based on
    consecutive failure counts. Returns sources that were newly disabled
    this run (so the caller can send a distinct, more urgent alert)."""
    newly_disabled: list[Source] = []

    sources = (
        await session.execute(
            select(Source).where(Source.status != SourceStatus.DISABLED)
        )
    ).scalars().all()

    for source in sources:
        if source.consecutive_failures >= DISABLE_FAILURE_THRESHOLD:
            if source.status != SourceStatus.DISABLED:
                source.status = SourceStatus.DISABLED
                newly_disabled.append(source)
                log.error(
                    "source_auto_disabled",
                    source=source.name,
                    consecutive_failures=source.consecutive_failures,
                )
        elif source.consecutive_failures >= DEGRADED_FAILURE_THRESHOLD:
            source.status = SourceStatus.DEGRADED
        else:
            source.status = SourceStatus.ACTIVE

    return newly_disabled
