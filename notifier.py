"""Admin alert delivery via Telegram DM.

Used by both the worker (scraper failures, staleness, reconciliation
review) and the bot (e.g. an admin command erroring). Uses a standalone
`aiogram.Bot` instance rather than the full `Dispatcher` — sending a
message doesn't need routing/handlers, and the worker process has no
Dispatcher at all.
"""

from __future__ import annotations

import hashlib

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from core.config import settings
from core.logging import get_logger
from core.redis_client import get_redis

log = get_logger(__name__)

# Identical alerts (same dedup key) within this window are suppressed after
# the first send, so e.g. a source failing every 5-minute scrape cycle for
# hours doesn't send hundreds of identical Telegram messages.
_DEDUP_TTL_SECONDS = 30 * 60

_bot: Bot | None = None


def _get_bot() -> Bot:
    global _bot
    if _bot is None:
        if not settings.telegram_bot_token:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN is not configured — cannot send admin alerts"
            )
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


def _dedup_key(message: str) -> str:
    digest = hashlib.sha256(message.encode()).hexdigest()[:16]
    return f"alert-dedup:{digest}"


async def notify_admins(message: str, *, dedup: bool = True) -> None:
    """Send `message` to every configured admin Telegram ID.

    If `dedup` is True (default), identical messages are suppressed for
    `_DEDUP_TTL_SECONDS` after the first send. Set `dedup=False` for
    alerts where every occurrence matters regardless of repetition.
    """
    if not settings.admin_ids:
        log.warning("no_admin_ids_configured", message=message)
        return

    if dedup:
        redis = get_redis()
        key = _dedup_key(message)
        # SET ... NX EX: only "acquires" (and thus proceeds) the first time;
        # subsequent identical alerts within the TTL are silently dropped.
        acquired = await redis.set(key, "1", nx=True, ex=_DEDUP_TTL_SECONDS)
        if not acquired:
            log.debug("admin_alert_deduped", message=message)
            return

    bot = _get_bot()
    text = f"⚠️ Kurdistan Finance Bot Alert\n\n{message}"

    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except TelegramAPIError as exc:
            # Never let a failed admin notification crash the caller (a
            # scrape job, a reconciliation run) — log and move on.
            log.error("admin_alert_delivery_failed", admin_id=admin_id, error=str(exc))


async def close_notifier_bot() -> None:
    """Release the standalone Bot's HTTP session. Call on process shutdown."""
    global _bot
    if _bot is not None:
        await _bot.session.close()
        _bot = None
