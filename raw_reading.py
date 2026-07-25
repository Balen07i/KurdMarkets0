"""RawReading — one immutable record of a single scrape result.

Every value a scraper retrieves is written here BEFORE reconciliation runs,
and rows are never updated or deleted (only `status` transitions). This is
the permanent audit trail the spec requires: given any published rate, an
admin can always trace back to exactly which raw readings produced it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.enums import ReadingStatus
from core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.asset import Asset
    from core.models.source import Source


class RawReading(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single value read from a single source at a single point in time.

    Never mutated after insert except for `status` (pending -> reconciled
    / rejected), which reconciliation sets once it decides how this
    reading was used.
    """

    __tablename__ = "raw_readings"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Numeric(18, 6) comfortably covers both large IQD-denominated prices
    # and small crypto/precious-metal fractional prices without float
    # rounding error — money/rate values must never be stored as float.
    value: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    # When the source claims this price was valid (may differ from
    # `created_at`, which is when *we* scraped it).
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[ReadingStatus] = mapped_column(
        Enum(ReadingStatus, name="reading_status", native_enum=True),
        default=ReadingStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Free-form snapshot of whatever the scraper saw (raw HTML fragment,
    # API JSON, etc.) for debugging when a source changes format. Kept
    # small/bounded by each scraper — this is a debugging aid, not a full
    # page dump.
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Populated by reconciliation if this reading was excluded as an
    # outlier, e.g. "deviates 8.2% from median of 3 sources".
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="raw_readings")
    source: Mapped["Source"] = relationship(back_populates="raw_readings")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RawReading asset_id={self.asset_id} value={self.value} status={self.status!r}>"
