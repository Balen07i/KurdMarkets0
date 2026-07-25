"""Reconciliation job — for every asset in a category with pending
(unreconciled) raw readings, run the reconciliation engine and publish (or
flag) the result.

Runs immediately after `scrape.py` for the same category (see
worker/scheduler.py), so there is minimal delay between "data collected"
and "data verified/published".
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.config import settings
from core.db import session_scope
from core.enums import AssetCategory, PublicationStatus, ReadingStatus
from core.logging import get_logger
from core.models import Asset, RawReading
from monitoring.notifier import notify_admins
from reconciliation.engine import CandidateReading, reconcile
from reconciliation.publisher import publish_reconciliation_result
from worker.jobs.alerts import check_and_trigger_alerts

log = get_logger(__name__)


async def reconcile_category(category: AssetCategory) -> int:
    """Reconcile every asset in `category` that has pending raw readings.

    Returns the number of assets reconciled (published or flagged), for
    logging/metrics.
    """
    reconciled_count = 0

    async with session_scope() as session:
        assets = (
            await session.execute(
                select(Asset).where(Asset.category == category, Asset.is_active.is_(True))
            )
        ).scalars().all()

        for asset in assets:
            pending = (
                await session.execute(
                    select(RawReading)
                    .where(
                        RawReading.asset_id == asset.id,
                        RawReading.status == ReadingStatus.PENDING,
                    )
                    .options(selectinload(RawReading.source))
                )
            ).scalars().all()

            if not pending:
                continue

            candidates = [
                CandidateReading(
                    reading_id=r.id,
                    source_id=r.source_id,
                    source_name=r.source.name if r.source else "unknown",
                    trust_weight=r.source.trust_weight if r.source else 1.0,
                    value=float(r.value),
                    observed_at=r.observed_at,
                )
                for r in pending
            ]

            result = reconcile(candidates)

            published_rate = await publish_reconciliation_result(
                session, asset, result, mithqal_grams=settings.mithqal_grams
            )
            reconciled_count += 1

            if result.status == PublicationStatus.PUBLISHED:
                await check_and_trigger_alerts(session, asset, published_rate)
            else:
                await notify_admins(
                    f"Rate flagged for review: {asset.name_en} ({asset.code})\n"
                    f"Reason: {result.review_reason}"
                )

    log.info(
        "reconcile_category_complete",
        category=category.value,
        assets_reconciled=reconciled_count,
    )
    return reconciled_count
