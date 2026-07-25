"""Category -> asset list -> asset detail -> history browsing flow.

This is the bot's core "just show me the verified data" feature — every
handler here reads exclusively through `history/rates.py`, never
constructing its own query against `PublishedRate`/`RawReading`.
"""

from __future__ import annotations

from datetime import timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.formatting import format_asset_detail, format_history_line
from bot.keyboards.menus import (
    CB_ASSET,
    CB_BACK_MAIN,
    CB_CATEGORY,
    CB_HISTORY,
    asset_detail_keyboard,
    asset_list_keyboard,
    back_to_main_keyboard,
    main_menu_keyboard,
)
from core.enums import AssetCategory
from core.logging import get_logger
from core.time import now_utc
from history.rates import get_asset_by_code, get_current_rate, get_historical_rates, list_active_assets

log = get_logger(__name__)

router = Router(name="rates")

_WELCOME_TEXT = (
    "👋 بەخێربێیت بۆ بۆتی دارایی کوردستان!\n\n" "لە خوارەوە بەشێک هەڵبژێرە:"
)


@router.callback_query(F.data == CB_BACK_MAIN)
async def handle_back_to_main(callback: CallbackQuery) -> None:
    await callback.message.edit_text(_WELCOME_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CB_CATEGORY}:"))
async def handle_category_selected(callback: CallbackQuery, session: AsyncSession) -> None:
    category_value = callback.data.split(":", 1)[1]
    try:
        category = AssetCategory(category_value)
    except ValueError:
        await callback.answer("Unknown category", show_alert=True)
        return

    assets = await list_active_assets(session, category=category)
    if not assets:
        await callback.answer("هیچ شتێک لەم بەشەدا نییە.", show_alert=True)
        return

    await callback.message.edit_text(
        f"بەشی هەڵبژێردراو — یەکێک هەڵبژێرە بۆ بینینی نرخ:",
        reply_markup=asset_list_keyboard(assets),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CB_ASSET}:"))
async def handle_asset_selected(callback: CallbackQuery, session: AsyncSession) -> None:
    asset_code = callback.data.split(":", 1)[1]
    asset = await get_asset_by_code(session, asset_code)
    if asset is None:
        await callback.answer("Asset not found", show_alert=True)
        return

    rate = await get_current_rate(session, asset)
    text = format_asset_detail(asset, rate)

    await callback.message.edit_text(
        text, reply_markup=asset_detail_keyboard(asset), parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CB_HISTORY}:"))
async def handle_history_requested(callback: CallbackQuery, session: AsyncSession) -> None:
    asset_code = callback.data.split(":", 1)[1]
    asset = await get_asset_by_code(session, asset_code)
    if asset is None:
        await callback.answer("Asset not found", show_alert=True)
        return

    since = now_utc() - timedelta(days=7)
    history = await get_historical_rates(session, asset, since=since, limit=15)

    if not history:
        await callback.answer("هیچ مێژوویەک بەردەست نییە.", show_alert=True)
        return

    lines = [f"*مێژووی {asset.name_ckb} (٧ ڕۆژی ڕابردوو)*", ""]
    lines.extend(format_history_line(r) for r in history)

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_to_main_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()
