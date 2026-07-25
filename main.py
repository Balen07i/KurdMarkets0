"""Telegram bot process entrypoint.

Run with: `python -m bot.main`
This is Railway's DEFAULT service (see railway.toml). Runs long-polling
(no public URL/webhook required) plus a tiny aiohttp `/health` endpoint so
Railway's health check (`healthcheckPath = "/health"` in railway.toml) has
something to hit — long-polling alone exposes no HTTP port.
"""

from __future__ import annotations

import asyncio
import os
import signal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiohttp import web

from bot.handlers import admin, alerts, rates, start, summary
from bot.middlewares.db import DbSessionMiddleware
from core.config import settings
from core.db import check_db_connection, dispose_engine
from core.exceptions import ConfigurationError
from core.logging import configure_logging, get_logger
from core.redis_client import check_redis_connection, close_redis, get_redis

log = get_logger(__name__)


def _validate_required_config() -> None:
    if not settings.telegram_bot_token:
        raise ConfigurationError(
            "TELEGRAM_BOT_TOKEN is not configured. See .env.example."
        )


def build_dispatcher() -> Dispatcher:
    storage = RedisStorage(redis=get_redis())
    dispatcher = Dispatcher(storage=storage)

    dispatcher.message.middleware(DbSessionMiddleware())
    dispatcher.callback_query.middleware(DbSessionMiddleware())

    # Order matters: admin routes are checked first only for /admin and its
    # callbacks (its own IsAdmin filter scopes it), then general browsing,
    # alerts, summary, and finally /start last so more specific commands
    # elsewhere aren't shadowed by a broad catch-all (there isn't one here,
    # but this ordering is the project convention for when one gets added).
    dispatcher.include_router(admin.router)
    dispatcher.include_router(rates.router)
    dispatcher.include_router(alerts.router)
    dispatcher.include_router(summary.router)
    dispatcher.include_router(start.router)

    return dispatcher


async def _health_handler(request: web.Request) -> web.Response:
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    healthy = db_ok and redis_ok
    return web.json_response(
        {"status": "ok" if healthy else "unhealthy", "db": db_ok, "redis": redis_ok},
        status=200 if healthy else 503,
    )


async def _run_health_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/health", _health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", "8080"))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    log.info("health_server_started", port=port)
    return runner


async def main() -> None:
    configure_logging()
    log.info("bot_starting", env=settings.app_env)

    _validate_required_config()

    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    if not db_ok or not redis_ok:
        log.error("startup_health_check_failed", db_ok=db_ok, redis_ok=redis_ok)
        raise SystemExit(1)

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = build_dispatcher()

    health_runner = await _run_health_server()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    polling_task = asyncio.create_task(dispatcher.start_polling(bot, handle_signals=False))
    log.info("bot_started")

    await stop_event.wait()

    log.info("bot_shutting_down")
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass

    await dispatcher.storage.close()
    await bot.session.close()
    await health_runner.cleanup()
    await close_redis()
    await dispose_engine()
    log.info("bot_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
