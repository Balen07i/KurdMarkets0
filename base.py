"""Declarative base + shared mixins for all ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base. Import this (not a per-file Base) so every
    model registers on the same metadata — required for Alembic
    autogenerate to see all tables."""

    pass


class UUIDPrimaryKeyMixin:
    """Use UUID primary keys instead of auto-increment integers.

    Chosen so raw reading / published rate IDs are safe to reference in
    external logs, admin URLs, and API responses without leaking row-count
    information, and so they can be generated client-side before insert.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """Adds created_at / updated_at columns, maintained by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
