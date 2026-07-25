"""User — a Telegram bot user."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.enums import Language
from core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.alert import Alert


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Telegram's user ID — BigInteger because Telegram IDs now exceed
    # 32-bit signed int range.
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)

    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    language: Mapped[Language] = mapped_column(
        Enum(Language, name="language", native_enum=True), default=Language.CKB, nullable=False
    )

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True if the user has blocked the bot (set when a send fails with 'bot was blocked').",
    )

    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User telegram_id={self.telegram_id} username={self.username!r}>"
