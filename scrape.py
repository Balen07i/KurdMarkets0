"""Scrape job — runs every active Source for one AssetCategory, persists
each result as a RawReading, and tracks per-source health.

Deliberately isolates failures per-source: one source raising
`ScraperError` must never prevent other sources (for the same or other
assets) from being scraped in the same cycle.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.db import session_scope
from core.enums import AssetCategory, SourceStatus
from core.exceptions import ScraperError
from core.logging import get_logger
from core.models import Asset, RawReading, Source
from core.time import now_utc
from monitoring.health import apply_source_status_transitions
from monitoring.notifier import notify_admins
from providers.registry import ProviderResolutionError, instantiate_provider

log = get_logger(__name__)


async def scrape_category(category: AssetCategory) -> int:
    """Run every active source whose asset belongs to `category`.

    Returns the number of RawReading rows written, for logging/metrics.
    """
    written = 0

    async with session_scope() as session:
        sources = (
            await session.execute(
                select(Source)
                .join(Asset, Source.asset_id == Asset.id)
                .where(
                    Asset.category == category,
                    Asset.is_active.is_(True),
                    Source.status != SourceStatus.DISABLED,
                )
                .options(selectinload(Source.asset))
            )
        ).scalars().all()

        if not sources:
            log.warning("scrape_no_active_sources", category=category.value)
            return 0

        # Cache Asset lookups by code within this run — a single provider
        # call (e.g. CoinGecko) commonly returns readings for several
        # assets at once, all needing the same code -> Asset resolution.
        assets_by_code = {
            asset.code: asset
            for asset in (
                await session.execute(select(Asset).where(Asset.category == category))
            ).scalars()
        }

        for source in sources:
            try:
                provider = instantiate_provider(source.provider_path)
            except ProviderResolutionError as exc:
                log.error("provider_resolution_failed", source=source.name, error=str(exc))
                await notify_admins(
                    f"Source '{source.name}' has an invalid provider_path "
                    f"({source.provider_path!r}): {exc}"
                )
                continue

            try:
                readings = await provider.fetch()
            except ScraperError as exc:
                _record_failure(source, exc)
                log.error(
                    "scrape_failed",
                    source=source.name,
                    provider=source.provider_path,
                    error=str(exc),
                    consecutive_failures=source.consecutive_failures,
                )
                await notify_admins(
                    f"Scraper failed: source '{source.name}' "
                    f"({source.provider_path}) — {exc}\n"
                    f"Consecutive failures: {source.consecutive_failures}"
                )
                continue
            except Exception as exc:  # noqa: BLE001 - unexpected bug in a provider
                _record_failure(source, exc)
                log.exception("scrape_unexpected_error", source=source.name)
                await notify_admins(
                    f"Unexpected error in source '{source.name}': {exc}"
                )
                continue

            source.consecutive_failures = 0
            source.last_success_at = now_utc()
            source.last_error = None

            for reading in readings:
                asset = assets_by_code.get(reading.asset_code.value)
                if asset is None:
                    log.warning(
                        "scrape_reading_unknown_asset",
                        source=source.name,
                        asset_code=reading.asset_code.value,
                    )
                    continue

                session.add(
                    RawReading(
                        asset_id=asset.id,
                        source_id=source.id,
                        value=reading.value,
                        currency=reading.currency,
                        observed_at=reading.observed_at,
                        raw_payload=reading.raw_payload,
                    )
                )
                written += 1

        newly_disabled = await apply_source_status_transitions(session)
        for source in newly_disabled:
            await notify_admins(
                f"Source '{source.name}' has been AUTO-DISABLED after "
                f"{source.consecutive_failures} consecutive failures. "
                f"An admin must re-enable it after fixing the underlying issue.",
                dedup=False,
            )

    log.info("scrape_category_complete", category=category.value, readings_written=written)
    return written


def _record_failure(source: Source, exc: Exception) -> None:
    source.consecutive_failures += 1
    source.last_failure_at = now_utc()
    source.last_error = str(exc)[:2000]
