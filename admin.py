"""Admin review workflow: list rates flagged PENDING_REVIEW by
reconciliation, approve or reject each one.

All handlers here are gated by `IsAdmin` — see bot/filters.py. This is the
human-in-the-loop step the spec requires: "If sources disagree
significantly: Do NOT publish automatically. Flag for administrator
review."
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.filters import IsAdmin
from bot.formatting import format_price
from bot.keyboards.menus import CB_ADMIN_APPROVE, CB_ADMIN_REJECT, admin_review_keyboard
from core.enums import PublicationStatus
from core.logging import get_logger
from core.models import PublishedRate
from core.time import format_local
from reconciliation.publisher import resolve_admin_review

log = get_logger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

_MAX_LISTED = 10


def _format_review_card(rate: PublishedRate) -> str:
    asset_name = rate.asset.name_en if rate.asset else "unknown asset"
    candidate_price = rate.reconciliation_meta.get("final_price") if rate.reconciliation_meta else None
    price_line = (
        f"Candidate price: {format_price(float(candidate_price))}"
        if candidate_price is not None
        else "No candidate price could be computed"
    )
    return (
        f"⚠️ *Pending Review*: {asset_name}\n\n"
        f"{price_line}\n"
        f"Reason: {rate.review_reason}\n"
        f"Flagged at: {format_local(rate.created_at)}\n"
        f"ID: `{rate.id}`"
    )


@router.message(Command("admin"))
async def list_pending_reviews(message: Message, session: AsyncSession) -> None:
    pending = (
        await session.execute(
            select(PublishedRate)
            .where(PublishedRate.status == PublicationStatus.PENDING_REVIEW)
            .options(selectinload(PublishedRate.asset))
            .order_by(PublishedRate.created_at.desc())
            .limit(_MAX_LISTED)
        )
    ).scalars().all()

    if not pending:
        await message.answer("✅ No rates are currently pending review.")
        return

    for rate in pending:
        await message.answer(
            _format_review_card(rate),
            reply_markup=admin_review_keyboard(str(rate.id)),
            parse_mode="Markdown",
        )


@router.callback_query(F.data.startswith(f"{CB_ADMIN_APPROVE}:"))
async def approve_rate(callback: CallbackQuery, session: AsyncSession) -> None:
    rate_id = callback.data.split(":", 1)[1]
    rate = await session.get(PublishedRate, rate_id)
    if rate is None or rate.status != PublicationStatus.PENDING_REVIEW:
        await callback.answer("This rate is no longer pending review.", show_alert=True)
        return

    await resolve_admin_review(
        session, rate, approve=True, admin_telegram_id=callback.from_user.id
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ APPROVED — now live.", parse_mode=None
    )
    await callback.answer("Approved")


@router.callback_query(F.data.startswith(f"{CB_ADMIN_REJECT}:"))
async def reject_rate(callback: CallbackQuery, session: AsyncSession) -> None:
    rate_id = callback.data.split(":", 1)[1]
    rate = await session.get(PublishedRate, rate_id)
    if rate is None or rate.status != PublicationStatus.PENDING_REVIEW:
        await callback.answer("This rate is no longer pending review.", show_alert=True)
        return

    await resolve_admin_review(
        session, rate, approve=False, admin_telegram_id=callback.from_user.id
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ REJECTED.", parse_mode=None
    )
    await callback.answer("Rejected")
