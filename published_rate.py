"""PublishedRate — the single source of truth the bot and AI are allowed
to read.

A row here is only ever created by the reconciliation engine, never
directly by a scraper. This is what enforces "the AI only reads published
rates" and "the bot never scrapes data directly" at the data layer, not
just by convention.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.enums import PublicationStatus
from core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.asset import Asset


class PublishedRate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A verified, publishable price point for one asset at one point in
    time. The bot's "current price" view is always the latest row per
    asset (by `effective_at`); the `/history` feature queries this table
    across time directly — no separate history table is needed since this
    table already *is* an append-only history.
    """

    __tablename__ = "published_rates"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Primary published value, denominated in Asset.base_unit.
    price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)

    # For gold/silver only: the same price expressed per gram in addition
    # to the primary per-mithqal price stored in `price`. NULL for
    # currency/fuel/crypto assets. Kept as explicit columns (rather than a
    # generic unit-conversion table) since exactly two units ever apply
    # here and a generic system would add indirection without real value.
    price_per_gram: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)

    daily_change_pct: Mapped[float | None] = mapped_column(Numeric(9, 4), nullable=True)
    daily_change_abs: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)

    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    status: Mapped[PublicationStatus] = mapped_column(
        Enum(PublicationStatus, name="publication_status", native_enum=True),
        default=PublicationStatus.PUBLISHED,
        nullable=False,
        index=True,
    )

    # 0.0-1.0 confidence score computed during reconciliation (based on
    # source agreement, source count, and source trust weights).
    confidence_score: Mapped[float] = mapped_column(nullable=False, default=1.0)

    # IDs of the RawReading rows that fed into this publication, for full
    # traceability without a join table (order doesn't matter, so a plain
    # UUID array is simpler than an association table here).
    source_reading_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )

    # If PENDING_REVIEW/REJECTED, why reconciliation could not auto-publish
    # (e.g. "sources disagree by 6.1%, tolerance is 1.5%").
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_admin_id: Mapped[int | None] = mapped_column(nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Free-form reconciliation metadata for debugging/audit: per-source
    # values considered, median, tolerance band used, etc.
    reconciliation_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="published_rates")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<PublishedRate asset_id={self.asset_id} price={self.price} "
            f"status={self.status!r} confidence={self.confidence_score}>"
        )
