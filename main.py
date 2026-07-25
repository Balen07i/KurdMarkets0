"""Worker process entrypoint.

Run with: `python -m worker.main`
On Railway, this is the SECOND service's start command (the default
`railway.toml` configures the bot; override the worker service's start
command in the Railway dashboard — see docs/DEPLOYMENT.md).
"""

from __future__ import annotations

import asyncio
import signal

from core.config import settings
from core.db import check_db_connection, dispose_engine
from core.exceptions import ConfigurationError
from core.logging import configure_logging, get_logger
from core.redis_client import check_redis_connection, close_redis
from monitoring.notifier import close_notifier_bot
from worker.jobs.alerts import close_alerts_bot
from worker.scheduler import build_scheduler

log = get_logger(__name__)


def _validate_required_config() -> None:
    """Fail fast and loudly on missing required secrets, instead of
    starting up and failing confusingly on the first scheduled job."""
    missing = []
    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.anthropic_api_key:
        # Not fatal for scraping/reconciliation to work, but the daily
        # summary job will fail every day without it — warn loudly rather
        # than silently skipping.
        log.warning(
            "anthropic_api_key_missing",
            note="AI daily summary generation will fail until ANTHROPIC_API_KEY is set",
        )
    if missing:
        raise ConfigurationError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"See .env.example."
        )


async def main() -> None:
    configure_logging()
    log.info("worker_starting", env=settings.app_env)

    _validate_required_config()

    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    if not db_ok or not redis_ok:
        log.error("startup_health_check_failed", db_ok=db_ok, redis_ok=redis_ok)
        raise SystemExit(1)

    scheduler = build_scheduler()
    scheduler.start()
    log.info("worker_started")

    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()

    log.info("worker_shutting_down")
    scheduler.shutdown(wait=True)
    await close_notifier_bot()
    await close_alerts_bot()
    await close_redis()
    await dispose_engine()
    log.info("worker_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
