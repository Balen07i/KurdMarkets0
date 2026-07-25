"""Daily AI summary job — generates (once) and caches the day's Kurdish
market summary. Scheduled once per day at `settings.ai_summary_hour` local
time (see worker/scheduler.py), but also safe to call more than once (see
`get_or_generate_daily_summary`'s idempotency) in case of a missed run or
manual re-trigger via an admin command.
"""

from __future__ import annotations

from core.db import session_scope
from core.exceptions import AISummaryError, ConfigurationError
from core.logging import get_logger
from history.ai_summary import get_or_generate_daily_summary
from monitoring.notifier import notify_admins

log = get_logger(__name__)


async def generate_daily_summary_job() -> None:
    async with session_scope() as session:
        try:
            summary = await get_or_generate_daily_summary(session)
            log.info("daily_summary_job_complete", date=summary.summary_date.isoformat())
        except (AISummaryError, ConfigurationError) as exc:
            log.error("daily_summary_job_failed", error=str(exc))
            await notify_admins(f"Daily AI summary generation failed: {exc}")
