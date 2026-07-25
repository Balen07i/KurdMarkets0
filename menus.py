"""Inline keyboard builders.

Centralized here so callback_data formats are defined once and reused by
both the handler that sends a keyboard and the handler that receives its
callback — avoiding subtle "typo in a callback_data string" bugs spread
across files.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.enums import AssetCategory
from core.models import Asset

# --- Callback data prefixes ---------------------------------------------
CB_CATEGORY = "cat"       # cat:<category>
CB_ASSET = "asset"        # asset:<asset_code>
CB_HISTORY = "hist"       # hist:<asset_code>
CB_ALERT_SET = "alertset"  # alertset:<asset_code>
CB_ALERT_LIST = "alertlist"
CB_ALERT_CANCEL = "alertcancel"  # alertcancel:<alert_id>
CB_BACK_MAIN = "backmain"
CB_ADMIN_APPROVE = "adminappr"  # adminappr:<published_rate_id>
CB_ADMIN_REJECT = "adminrej"    # adminrej:<published_rate_id>

_CATEGORY_EMOJI: dict[AssetCategory, str] = {
    AssetCategory.CURRENCY: "💵",
    AssetCategory.GOLD: "🥇",
    AssetCategory.SILVER: "🥈",
    AssetCategory.FUEL: "⛽",
    AssetCategory.CRYPTO: "₿",
}

_CATEGORY_LABEL_CKB: dict[AssetCategory, str] = {
    AssetCategory.CURRENCY: "دراو",
    AssetCategory.GOLD: "زێڕ",
    AssetCategory.SILVER: "زیو",
    AssetCategory.FUEL: "سووتەمەنی",
    AssetCategory.CRYPTO: "کریپتۆ",
}


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in AssetCategory:
        emoji = _CATEGORY_EMOJI[category]
        label = _CATEGORY_LABEL_CKB[category]
        builder.button(text=f"{emoji} {label}", callback_data=f"{CB_CATEGORY}:{category.value}")
    builder.adjust(2)
    return builder.as_markup()


def asset_list_keyboard(assets: list[Asset]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for asset in assets:
        builder.button(text=asset.name_ckb, callback_data=f"{CB_ASSET}:{asset.code}")
    builder.button(text="⬅️ گەڕانەوە", callback_data=CB_BACK_MAIN)
    builder.adjust(2)
    return builder.as_markup()


def asset_detail_keyboard(asset: Asset) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📈 مێژوو", callback_data=f"{CB_HISTORY}:{asset.code}")
    builder.button(text="🔔 ئاگاداری دابنێ", callback_data=f"{CB_ALERT_SET}:{asset.code}")
    builder.button(text="⬅️ گەڕانەوە", callback_data=f"{CB_CATEGORY}:{asset.category.value}")
    builder.adjust(2, 1)
    return builder.as_markup()


def admin_review_keyboard(published_rate_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve", callback_data=f"{CB_ADMIN_APPROVE}:{published_rate_id}")
    builder.button(text="❌ Reject", callback_data=f"{CB_ADMIN_REJECT}:{published_rate_id}")
    builder.adjust(2)
    return builder.as_markup()


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ گەڕانەوە", callback_data=CB_BACK_MAIN)]]
    )
