"""Source — an independent origin of price data (a specific scraper/API).

Multiple Sources feed into reconciliation for the same Asset. Keeping
Source as its own table (rather than a string column on RawReading) lets us
track per-source health (failure streaks, last success) for monitoring and
for automatically down-weighting or disabling flaky sources.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.enums import SourceStatus
from core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.asset import Asset
    from core.models.raw_reading import RawReading


class Source(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A specific scraper or API configured to read one asset's price.

    Example rows: "cbi_official_website" (for USD_IQD_OFFICIAL),
    "sulaymaniyah_exchange_telegram" and "erbil_gold_market_site" (both
    feeding USD_IQD_LOCAL), "coingecko_api" (for all crypto assets).
    """

    __tablename__ = "sources"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Dotted path to the provider class responsible for this source, e.g.
    # "providers.currency.cbi_official.CBIOfficialProvider". Lets the
    # scheduler dynamically resolve which provider to run without a big
    # if/elif chain, and lets new sources be added via a DB row + a new
    # provider file, without touching the scheduler.
    provider_path: Mapped[str] = mapped_column(String(256), nullable=False)

    # Relative trust weight used in weighted-median reconciliation
    # (0.0-1.0+; 1.0 is a "normal" fully-trusted source). Manually tuned by
    # admins over time as sources prove reliable or unreliable.
    trust_weight: Mapped[float] = mapped_column(default=1.0, nullable=False)

    status: Mapped[SourceStatus] = mapped_column(
        Enum(SourceStatus, name="source_status", native_enum=True),
        default=SourceStatus.ACTIVE,
        nullable=False,
    )

    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="sources")
    raw_readings: Mapped[list["RawReading"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Source name={self.name!r} status={self.status!r}>"
