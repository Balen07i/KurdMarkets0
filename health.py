"""Health-check job — runs on a schedule, alerts admins about stale data
and degraded/disabled sources. Complements the per-scrape-cycle alerting
already done in `worker/jobs/scrape.py` (immediate failure alerts) by
catching slower-moving problems: an asset that hasn't published in hours
even though its scraper "succeeds" (e.g. because reconciliation keeps
flagging it for review).
"""

from __future__ import annotations

from core.db import session_scope
from core.logging import get_logger
from monitoring.health import find_stale_assets, find_unhealthy_sources
from monitoring.notifier import notify_admins

log = get_logger(__name__)


async def run_health_check_job() -> None:
    async with session_scope() as session:
        stale = await find_stale_assets(session)
        unhealthy = await find_unhealthy_sources(session)

    if stale:
        lines = "\n".join(
            f"- {a.asset_name_en}: "
            + ("never published" if a.minutes_since_update == float("inf") else f"{a.minutes_since_update:.0f} min old")
            for a in stale
        )
        await notify_admins(f"Stale data detected for {len(stale)} asset(s):\n{lines}")
        log.warning("stale_assets_detected", count=len(stale))

    if unhealthy:
        lines = "\n".join(
            f"- {s.source_name} ({s.asset_code}): {s.consecutive_failures} consecutive "
            f"failures — {s.last_error or 'no error message'}"
            for s in unhealthy
        )
        await notify_admins(f"{len(unhealthy)} source(s) reporting failures:\n{lines}")
        log.warning("unhealthy_sources_detected", count=len(unhealthy))
