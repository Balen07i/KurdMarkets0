"""Alert checking — fires user-configured price alerts immediately after a
new PublishedRate is written, rather than on a separate poll loop, so
alerts trigger within one scrape/reconcile cycle of the threshold being
crossed.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.enums import AlertDirection, AlertStatus
from core.logging import get_logger
from core.models import Alert, Asset, PublishedRate, User
from core.time import now_utc

log = get_logger(__name__)

_bot: Bot | None = None


def _get_bot() -> Bot:
    global _bot
    if _bot is None:
        if not settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured — cannot send alerts")
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


async def check_and_trigger_alerts(
    session: AsyncSession, asset: Asset, rate: PublishedRate
) -> int:
    """Find every ACTIVE alert on `asset` whose threshold the new `rate`
    has crossed, notify the user, and mark it TRIGGERED.

    Returns the number of alerts triggered.
    """
    active_alerts = (
        await session.execute(
            select(Alert).where(Alert.asset_id == asset.id, Alert.status == AlertStatus.ACTIVE)
        )
    ).scalars().all()

    if not active_alerts:
        return 0

    price = float(rate.price)
    triggered = 0
    bot = _get_bot()

    for alert in active_alerts:
        threshold = float(alert.threshold)
        crossed = (
            (alert.direction == AlertDirection.ABOVE and price >= threshold)
            or (alert.direction == AlertDirection.BELOW and price <= threshold)
        )
        if not crossed:
            continue

        user = await session.get(User, alert.user_id)
        if user is None or user.is_blocked:
            alert.status = AlertStatus.TRIGGERED
            alert.triggered_at = now_utc()
            continue

        direction_word = "above" if alert.direction == AlertDirection.ABOVE else "below"
        text = (
            f"🔔 Price Alert: {asset.name_en}\n\n"
            f"Current price {price} has gone {direction_word} your threshold "
            f"of {threshold}."
        )

        try:
            await bot.send_message(chat_id=user.telegram_id, text=text)
        except TelegramAPIError as exc:
            log.warning("alert_delivery_failed", user_id=str(user.id), error=str(exc))
            if "bot was blocked" in str(exc).lower():
                user.is_blocked = True

        alert.status = AlertStatus.TRIGGERED
        alert.triggered_at = now_utc()
        triggered += 1

    if triggered:
        log.info("alerts_triggered", asset=asset.code, count=triggered)

    return triggered


async def close_alerts_bot() -> None:
    global _bot
    if _bot is not None:
        await _bot.session.close()
        _bot = None
