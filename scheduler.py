"""APScheduler configuration — wires every worker job to its schedule.

One `AsyncIOScheduler` running inside the worker process's asyncio event
loop. Each asset category gets its own scrape-then-reconcile job pair on
its own interval (see `.env.example` `SCRAPE_INTERVAL_*`), so e.g. crypto
(highly liquid, checked every 2 minutes) doesn't force fuel (checked every
30 minutes) onto the same cadence.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.config import settings
from core.enums import AssetCategory
from core.logging import get_logger
from worker.jobs.health import run_health_check_job
from worker.jobs.reconcile import reconcile_category
from worker.jobs.scrape import scrape_category
from worker.jobs.summary import generate_daily_summary_job

log = get_logger(__name__)

_CATEGORY_INTERVALS: dict[AssetCategory, int] = {
    AssetCategory.CURRENCY: settings.scrape_interval_currency,
    AssetCategory.GOLD: settings.scrape_interval_gold,
    AssetCategory.SILVER: settings.scrape_interval_silver,
    AssetCategory.FUEL: settings.scrape_interval_fuel,
    AssetCategory.CRYPTO: settings.scrape_interval_crypto,
}

# Health check runs independently of any single category's cadence.
_HEALTH_CHECK_INTERVAL_SECONDS = 15 * 60


async def _scrape_then_reconcile(category: AssetCategory) -> None:
    """Combined job: scrape all sources for a category, then immediately
    reconcile whatever was collected. Chained as one APScheduler job
    (rather than two independently-scheduled ones) so reconciliation
    always runs promptly after fresh data, never "in between" two
    unrelated scrape cycles.
    """
    try:
        await scrape_category(category)
    except Exception:  # noqa: BLE001 - a bug here must not kill the scheduler
        log.exception("scrape_job_crashed", category=category.value)
        return

    try:
        await reconcile_category(category)
    except Exception:  # noqa: BLE001
        log.exception("reconcile_job_crashed", category=category.value)


async def _health_check_wrapper() -> None:
    try:
        await run_health_check_job()
    except Exception:  # noqa: BLE001
        log.exception("health_check_job_crashed")


async def _summary_wrapper() -> None:
    try:
        await generate_daily_summary_job()
    except Exception:  # noqa: BLE001
        log.exception("summary_job_crashed")


def build_scheduler() -> AsyncIOScheduler:
    """Construct (but do not start) the process-wide scheduler with every
    job registered."""
    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    for category, interval_seconds in _CATEGORY_INTERVALS.items():
        scheduler.add_job(
            _scrape_then_reconcile,
            trigger=IntervalTrigger(seconds=interval_seconds),
            args=[category],
            id=f"scrape_reconcile_{category.value}",
            name=f"Scrape + reconcile: {category.value}",
            max_instances=1,  # never let a slow cycle overlap with the next
            coalesce=True,
            misfire_grace_time=interval_seconds,
        )

    scheduler.add_job(
        _health_check_wrapper,
        trigger=IntervalTrigger(seconds=_HEALTH_CHECK_INTERVAL_SECONDS),
        id="health_check",
        name="Health check: stale data + source health",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        _summary_wrapper,
        trigger=CronTrigger(hour=settings.ai_summary_hour, minute=0),
        id="daily_summary",
        name="Generate daily AI summary",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60 * 60,  # still run if we were down at 08:00
    )

    log.info(
        "scheduler_configured",
        jobs=[job.id for job in scheduler.get_jobs()],
        timezone=settings.timezone,
    )
    return scheduler
