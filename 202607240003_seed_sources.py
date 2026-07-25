"""seed sources

Revision ID: 202607240003
Revises: 202607240002
Create Date: 2026-07-24 00:03:00

Seeds the `sources` table, wiring each asset to the provider(s) that feed
it (see providers/registry.py for how `provider_path` is resolved at
runtime). Assets with two sources here can be auto-reconciled via median;
assets with only one configured source will always be flagged for admin
review by reconciliation (see reconciliation/engine.py) until a second
independent source is added — this is intentional: the spec requires
multiple independent sources before auto-publishing, so a single-sourced
asset is not silently trusted.

Uses a SELECT-based insert (`INSERT INTO sources (...) SELECT id, ... FROM
assets WHERE code = :code`) rather than looking up asset UUIDs in Python,
since the seed-assets migration (202607240002) generates those UUIDs
randomly at migration time and this migration has no other way to know
them.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "202607240003"
down_revision: Union[str, None] = "202607240002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (asset_code, source_name, provider_path)
SEED_SOURCES: list[tuple[str, str, str]] = [
    # --- Currency: official rate has exactly one authoritative source by
    # definition — it will always route to admin review until/unless a
    # second corroborating official-rate source is found, which is the
    # correct conservative behavior for an "official" figure.
    ("usd_iqd_official", "CBI Official Website", "providers.currency.cbi_official.CBIOfficialProvider"),
    ("usd_iqd_local", "Local Exchange Board 1", "providers.currency.local_market_site_one.LocalMarketSiteOneProvider"),
    ("usd_iqd_local", "Local Exchange Board 2", "providers.currency.local_market_site_two.LocalMarketSiteTwoProvider"),
    ("eur_iqd", "Local Exchange Board 1", "providers.currency.local_market_site_one.LocalMarketSiteOneProvider"),
    ("eur_iqd", "Local Exchange Board 2", "providers.currency.local_market_site_two.LocalMarketSiteTwoProvider"),
    ("try_iqd", "Local Exchange Board 1", "providers.currency.local_market_site_one.LocalMarketSiteOneProvider"),
    ("try_iqd", "Local Exchange Board 2", "providers.currency.local_market_site_two.LocalMarketSiteTwoProvider"),
    ("irt_iqd", "Local Exchange Board 1", "providers.currency.local_market_site_one.LocalMarketSiteOneProvider"),
    ("irt_iqd", "Local Exchange Board 2", "providers.currency.local_market_site_two.LocalMarketSiteTwoProvider"),
    # --- Gold ---------------------------------------------------------------
    ("gold_18k", "Local Gold Market 1", "providers.gold.local_market_site_one.GoldLocalMarketSiteOneProvider"),
    ("gold_18k", "Local Gold Market 2", "providers.gold.local_market_site_two.GoldLocalMarketSiteTwoProvider"),
    ("gold_21k", "Local Gold Market 1", "providers.gold.local_market_site_one.GoldLocalMarketSiteOneProvider"),
    ("gold_21k", "Local Gold Market 2", "providers.gold.local_market_site_two.GoldLocalMarketSiteTwoProvider"),
    ("gold_22k", "Local Gold Market 1", "providers.gold.local_market_site_one.GoldLocalMarketSiteOneProvider"),
    ("gold_22k", "Local Gold Market 2", "providers.gold.local_market_site_two.GoldLocalMarketSiteTwoProvider"),
    ("gold_24k", "Local Gold Market 1", "providers.gold.local_market_site_one.GoldLocalMarketSiteOneProvider"),
    ("gold_24k", "Local Gold Market 2", "providers.gold.local_market_site_two.GoldLocalMarketSiteTwoProvider"),
    ("gold_lira", "Local Gold Market 1", "providers.gold.local_market_site_one.GoldLocalMarketSiteOneProvider"),
    ("gold_lira", "Local Gold Market 2", "providers.gold.local_market_site_two.GoldLocalMarketSiteTwoProvider"),
    # --- Silver --------------------------------------------------------
    ("silver", "Local Silver Market 1", "providers.silver.local_market_site_one.SilverLocalMarketSiteOneProvider"),
    ("silver", "Local Silver Market 2", "providers.silver.local_market_site_two.SilverLocalMarketSiteTwoProvider"),
    # --- Fuel ---------------------------------------------------------------
    ("fuel_petrol", "Fuel Prices 1", "providers.fuel.site_one.FuelSiteOneProvider"),
    ("fuel_petrol", "Fuel Prices 2", "providers.fuel.site_two.FuelSiteTwoProvider"),
    ("fuel_diesel", "Fuel Prices 1", "providers.fuel.site_one.FuelSiteOneProvider"),
    ("fuel_diesel", "Fuel Prices 2", "providers.fuel.site_two.FuelSiteTwoProvider"),
    ("fuel_gas", "Fuel Prices 1", "providers.fuel.site_one.FuelSiteOneProvider"),
    ("fuel_gas", "Fuel Prices 2", "providers.fuel.site_two.FuelSiteTwoProvider"),
    # --- Crypto: both providers cover all five coins in one call each ----
    ("btc_usd", "CoinGecko API", "providers.crypto.coingecko.CoinGeckoProvider"),
    ("btc_usd", "Binance API", "providers.crypto.binance.BinanceProvider"),
    ("eth_usd", "CoinGecko API", "providers.crypto.coingecko.CoinGeckoProvider"),
    ("eth_usd", "Binance API", "providers.crypto.binance.BinanceProvider"),
    ("bnb_usd", "CoinGecko API", "providers.crypto.coingecko.CoinGeckoProvider"),
    ("bnb_usd", "Binance API", "providers.crypto.binance.BinanceProvider"),
    ("sol_usd", "CoinGecko API", "providers.crypto.coingecko.CoinGeckoProvider"),
    ("sol_usd", "Binance API", "providers.crypto.binance.BinanceProvider"),
    ("xrp_usd", "CoinGecko API", "providers.crypto.coingecko.CoinGeckoProvider"),
    ("xrp_usd", "Binance API", "providers.crypto.binance.BinanceProvider"),
]

_INSERT_SQL = sa.text(
    """
    INSERT INTO sources (id, asset_id, name, provider_path, trust_weight, status, consecutive_failures)
    SELECT gen_random_uuid(), assets.id, :name, :provider_path, 1.0, 'active', 0
    FROM assets
    WHERE assets.code = :code
    """
)

_DELETE_SQL = sa.text(
    """
    DELETE FROM sources
    USING assets
    WHERE sources.asset_id = assets.id
      AND assets.code = :code
      AND sources.name = :name
    """
)


def upgrade() -> None:
    # gen_random_uuid() requires pgcrypto (or Postgres 13+ has it
    # built-in via `gen_random_uuid()` from the `pgcrypto`/`pg_crypto`
    # extension on managed providers like Railway's Postgres, which ships
    # it enabled). Guard with CREATE EXTENSION IF NOT EXISTS for
    # portability across fresh databases.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    connection = op.get_bind()
    for code, name, provider_path in SEED_SOURCES:
        connection.execute(_INSERT_SQL, {"code": code, "name": name, "provider_path": provider_path})


def downgrade() -> None:
    connection = op.get_bind()
    for code, name, _ in SEED_SOURCES:
        connection.execute(_DELETE_SQL, {"code": code, "name": name})
