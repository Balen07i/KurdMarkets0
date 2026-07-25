"""Middleware injecting a fresh SQLAlchemy AsyncSession into every update's
handler data, scoped to that single update (commit on success, rollback on
handler exception) — the bot-side equivalent of `core.db.session_scope`.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from core.db import session_scope
from core.logging import get_logger

log = get_logger(__name__)


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with session_scope() as session:
            data["session"] = session
            return await handler(event, data)
