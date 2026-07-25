"""Asset — the registry of every financial instrument the bot tracks.

This table is the backbone of the "plugin" design: adding a new asset is a
data change (insert a row here + add an AssetCode enum member + write a
provider), not a schema or code-path change anywhere else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.enums import AssetCategory
from core.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from core.models.alert import Alert
    from core.models.published_rate import PublishedRate
    from core.models.raw_reading import RawReading
    from core.models.source import Source


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single trackable financial instrument, e.g. USD/IQD official rate,
    24K gold, or Bitcoin."""

    __tablename__ = "assets"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    category: Mapped[AssetCategory] = mapped_column(
        Enum(AssetCategory, name="asset_category", native_enum=True), nullable=False, index=True
    )

    # Display names — English + Central Kurdish (Sorani). The bot resolves
    # display strings from here so no user-facing name is ever hardcoded
    # in a handler.
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    name_ckb: Mapped[str] = mapped_column(String(128), nullable=False)

    # Base unit this asset's `PublishedRate.price` is denominated in, e.g.
    # "iqd" for USD/IQD, "usd" for BTC/USD. Secondary units (per-gram vs
    # per-mithqal for metals) are separate explicit columns on PublishedRate
    # rather than a generic unit-conversion system, since there are only
    # ever two for gold/silver and a generic system would add complexity
    # without real benefit here.
    base_unit: Mapped[str] = mapped_column(String(16), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Lower sort_order shows first in bot menus within a category.
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    sources: Mapped[list["Source"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    raw_readings: Mapped[list["RawReading"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    published_rates: Mapped[list["PublishedRate"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Asset code={self.code!r} category={self.category!r}>"
