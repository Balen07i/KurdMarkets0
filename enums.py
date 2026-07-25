"""Shared enums used across models, providers, and reconciliation.

Kept in `core` (rather than inside `core/models`) because providers and
reconciliation also need these without importing the ORM layer.
"""

from __future__ import annotations

import enum


class AssetCategory(str, enum.Enum):
    """Top-level plugin category. Every new asset type added later (e.g.
    real estate, another currency) gets one of these so bot menus,
    providers, and reconciliation can stay generic over category."""

    CURRENCY = "currency"
    GOLD = "gold"
    SILVER = "silver"
    FUEL = "fuel"
    CRYPTO = "crypto"


class AssetCode(str, enum.Enum):
    """Canonical identifier for each concrete asset. Stored on `Asset.code`.

    Adding a new asset means adding a value here plus a matching row in the
    `assets` table (seeded via Alembic data migration) plus a provider —
    nothing else needs to change.
    """

    # Currency
    USD_IQD_OFFICIAL = "usd_iqd_official"
    USD_IQD_LOCAL = "usd_iqd_local"
    EUR_IQD = "eur_iqd"
    TRY_IQD = "try_iqd"
    IRT_IQD = "irt_iqd"  # Iranian Toman

    # Gold (by karat) — price is always per-mithqal AND per-gram, both
    # stored on the same PublishedRate row (see models.published_rate).
    GOLD_18K = "gold_18k"
    GOLD_21K = "gold_21k"
    GOLD_22K = "gold_22k"
    GOLD_24K = "gold_24k"
    GOLD_LIRA = "gold_lira"

    # Silver
    SILVER = "silver"

    # Fuel
    FUEL_PETROL = "fuel_petrol"
    FUEL_DIESEL = "fuel_diesel"
    FUEL_GAS = "fuel_gas"

    # Crypto
    BTC_USD = "btc_usd"
    ETH_USD = "eth_usd"
    BNB_USD = "bnb_usd"
    SOL_USD = "sol_usd"
    XRP_USD = "xrp_usd"


class Unit(str, enum.Enum):
    IQD = "iqd"
    USD = "usd"
    MITHQAL = "mithqal"
    GRAM = "gram"
    LITER = "liter"


class ReadingStatus(str, enum.Enum):
    """Lifecycle of a single raw scraped reading."""

    PENDING = "pending"          # collected, not yet reconciled
    RECONCILED = "reconciled"    # used in a successful publication
    REJECTED = "rejected"        # excluded as an outlier during reconciliation


class PublicationStatus(str, enum.Enum):
    """Lifecycle of a published rate."""

    PUBLISHED = "published"              # auto-published, within tolerance
    PENDING_REVIEW = "pending_review"    # flagged, awaiting admin decision
    APPROVED = "approved"                # admin manually approved a flagged rate
    REJECTED = "rejected"                # admin rejected a flagged rate


class AlertDirection(str, enum.Enum):
    ABOVE = "above"
    BELOW = "below"


class AlertStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"


class SourceStatus(str, enum.Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"    # occasional failures, still trusted
    DISABLED = "disabled"    # manually or automatically disabled


class Language(str, enum.Enum):
    CKB = "ckb"  # Central Kurdish (Sorani)
    EN = "en"
    AR = "ar"
