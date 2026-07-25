"""Alert — a user-configured price threshold notification."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.enums import AlertDirection, AlertStatus
from core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.asset import Asset
    from core.models.user import User


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """"Notify me when USD/IQD local goes above/below X" style alert.

    Checked by the worker every time a new PublishedRate is written for
    the asset (see reconciliation/publisher.py), not on a separate poll
    loop — so alerts fire within one scrape cycle of the threshold being
    crossed.
    """

    __tablename__ = "alerts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    threshold: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    direction: Mapped[AlertDirection] = mapped_column(
        Enum(AlertDirection, name="alert_direction", native_enum=True), nullable=False
    )

    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status", native_enum=True),
        default=AlertStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="alerts")
    asset: Mapped["Asset"] = relationship(back_populates="alerts")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Alert user_id={self.user_id} asset_id={self.asset_id} "
            f"{self.direction.value} {self.threshold} status={self.status!r}>"
        )
