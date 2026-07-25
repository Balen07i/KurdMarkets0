"""Admin authorization filter.

Checks the static `TELEGRAM_ADMIN_IDS` env var (the always-trusted list,
useful before any `User` row even exists) OR the `users.is_admin` DB flag
(settable later without a redeploy, e.g. via a future admin-management
command). Either is sufficient.
"""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.models import User


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, session: AsyncSession) -> bool:
        user_id = _extract_user_id(event)
        if user_id is None:
            return False

        if user_id in settings.admin_ids:
            return True

        db_user = (
            await session.execute(select(User).where(User.telegram_id == user_id))
        ).scalar_one_or_none()
        return bool(db_user and db_user.is_admin)


def _extract_user_id(event: TelegramObject) -> int | None:
    from_user = getattr(event, "from_user", None)
    return from_user.id if from_user else None
