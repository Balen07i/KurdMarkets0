"""/start command — registers (or looks up) the user and shows the main
category menu.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.menus import main_menu_keyboard
from core.logging import get_logger
from core.models import User

log = get_logger(__name__)

router = Router(name="start")

_WELCOME_TEXT = (
    "👋 بەخێربێیت بۆ بۆتی دارایی کوردستان!\n\n"
    "نرخی دراو، زێڕ، زیو، سووتەمەنی و کریپتۆکەرەنسی بە کوردی، "
    "دووپاتکراوە و بەردەوام نوێدەکرێنەوە.\n\n"
    "لە خوارەوە بەشێک هەڵبژێرە:"
)


async def get_or_create_user(session: AsyncSession, telegram_user) -> User:  # type: ignore[no-untyped-def]
    """Look up a User by telegram_id, creating one on first contact.

    Shared by every handler that needs the current User row (not just
    /start) — a returning user who never technically "started" a fresh
    conversation (e.g. after a bot restart) still gets registered
    transparently on their first interaction.
    """
    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_user.id))
    ).scalar_one_or_none()

    if user is not None:
        # Keep denormalized profile fields fresh (username/name changes).
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        user.last_name = telegram_user.last_name
        return user

    user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
    )
    session.add(user)
    await session.flush()
    log.info("user_registered", telegram_id=telegram_user.id)
    return user


@router.message(CommandStart())
async def handle_start(message: Message, session: AsyncSession) -> None:
    await get_or_create_user(session, message.from_user)
    await message.answer(_WELCOME_TEXT, reply_markup=main_menu_keyboard())
