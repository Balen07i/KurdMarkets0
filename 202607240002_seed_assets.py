"""seed assets

Revision ID: 202607240002
Revises: 202607240001
Create Date: 2026-07-24 00:02:00

Seeds the `assets` table with every instrument listed in the product spec.
This is a DATA migration (not schema) — it is the canonical, versioned
definition of "which assets exist" so every environment (dev/staging/prod)
starts with the identical registry, and adding a new asset later is just a
new migration appending a row, matched with a new `AssetCode` enum member
and a new provider.
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import table, column

revision: str = "202607240002"
down_revision: Union[str, None] = "202607240001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


assets_table = table(
    "assets",
    column("id", postgresql.UUID(as_uuid=True)),
    column("category", sa.String()),
    column("code", sa.String()),
    column("name_en", sa.String()),
    column("name_ckb", sa.String()),
    column("base_unit", sa.String()),
    column("is_active", sa.Boolean()),
    column("sort_order", sa.Integer()),
)

# (category, code, name_en, name_ckb, base_unit, sort_order)
SEED_ASSETS: list[tuple[str, str, str, str, str, int]] = [
    # --- Currency ---------------------------------------------------------
    ("currency", "usd_iqd_official", "USD/IQD (Official)", "دۆلار/دینار (فەرمی)", "iqd", 10),
    ("currency", "usd_iqd_local", "USD/IQD (Local Market)", "دۆلار/دینار (بازاڕ)", "iqd", 20),
    ("currency", "eur_iqd", "EUR/IQD", "یۆرۆ/دینار", "iqd", 30),
    ("currency", "try_iqd", "Turkish Lira/IQD", "لیرەی تورکی/دینار", "iqd", 40),
    ("currency", "irt_iqd", "Iranian Toman/IQD", "تمەنی ئێران/دینار", "iqd", 50),
    # --- Gold ---------------------------------------------------------------
    ("gold", "gold_18k", "Gold 18K", "زێڕی ١٨ عەیار", "iqd", 10),
    ("gold", "gold_21k", "Gold 21K", "زێڕی ٢١ عەیار", "iqd", 20),
    ("gold", "gold_22k", "Gold 22K", "زێڕی ٢٢ عەیار", "iqd", 30),
    ("gold", "gold_24k", "Gold 24K", "زێڕی ٢٤ عەیار", "iqd", 40),
    ("gold", "gold_lira", "Gold Lira", "لیرەی زێڕ", "iqd", 50),
    # --- Silver --------------------------------------------------------
    ("silver", "silver", "Silver", "زیو", "iqd", 10),
    # --- Fuel --------------------------------------------------------------
    ("fuel", "fuel_petrol", "Petrol", "بەنزین", "iqd", 10),
    ("fuel", "fuel_diesel", "Diesel", "گازۆیل", "iqd", 20),
    ("fuel", "fuel_gas", "Cooking Gas", "گازی ماڵەوە", "iqd", 30),
    # --- Crypto ------------------------------------------------------------
    ("crypto", "btc_usd", "Bitcoin", "بیتکۆین", "usd", 10),
    ("crypto", "eth_usd", "Ethereum", "ئیثێریەم", "usd", 20),
    ("crypto", "bnb_usd", "BNB", "بی ئێن بی", "usd", 30),
    ("crypto", "sol_usd", "Solana", "سۆلانا", "usd", 40),
    ("crypto", "xrp_usd", "XRP", "ئێکس ئاڕ پی", "usd", 50),
]


def upgrade() -> None:
    op.bulk_insert(
        assets_table,
        [
            {
                "id": uuid.uuid4(),
                "category": category,
                "code": code,
                "name_en": name_en,
                "name_ckb": name_ckb,
                "base_unit": base_unit,
                "is_active": True,
                "sort_order": sort_order,
            }
            for category, code, name_en, name_ckb, base_unit, sort_order in SEED_ASSETS
        ],
    )


def downgrade() -> None:
    codes = [code for _, code, *_ in SEED_ASSETS]
    op.execute(
        assets_table.delete().where(assets_table.c.code.in_(codes))
    )
