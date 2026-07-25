"""Formatting helpers for user-facing bot messages.

Kept separate from handlers so the same formatting is used consistently
whether an asset is shown from the category list, a direct search, or an
alert notification.
"""

from __future__ import annotations

from core.models import Asset, PublishedRate
from core.time import format_local


def format_price(value: float) -> str:
    """Thousands-separated, up to 2 decimal places, trailing zeros trimmed."""
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"


def format_change(pct: float | None, abs_change: float | None) -> str:
    if pct is None:
        return "—"
    arrow = "🔺" if pct > 0 else ("🔻" if pct < 0 else "➖")
    sign = "+" if pct >= 0 else ""
    abs_part = f" ({sign}{format_price(abs_change)})" if abs_change is not None else ""
    return f"{arrow} {sign}{pct:.2f}%{abs_part}"


def format_asset_detail(asset: Asset, rate: PublishedRate | None) -> str:
    """Full detail card for one asset — current price, change, last
    updated. Shown when a user taps an asset from a category list."""
    if rate is None:
        return (
            f"*{asset.name_ckb}*\n\n"
            f"⚠️ هێشتا هیچ نرخێکی پشتڕاستکراوە بۆ ئەم بەشە نییە.\n"
            f"تکایە دواتر سەردانی بکەرەوە."
        )

    lines = [f"*{asset.name_ckb}*", ""]
    lines.append(f"💰 نرخ: `{format_price(float(rate.price))} {asset.base_unit.upper()}`")

    if rate.price_per_gram is not None:
        lines.append(f"⚖️ نرخی هەر گرامێک: `{format_price(float(rate.price_per_gram))} {asset.base_unit.upper()}`")

    lines.append(f"📊 گۆڕانکاری ڕۆژانە: {format_change(rate.daily_change_pct, rate.daily_change_abs)}")
    lines.append("")
    lines.append(f"🕒 دوایین نوێکردنەوە: {format_local(rate.effective_at, 'YYYY-MM-DD HH:mm')}")

    if rate.confidence_score < 0.9:
        lines.append("")
        lines.append("ℹ️ ئاگاداری: ئەم نرخە متمانەیەکی کەمتری هەیە (سەرچاوەکان جیاوازییان هەیە).")

    return "\n".join(lines)


def format_history_line(rate: PublishedRate) -> str:
    return f"{format_local(rate.effective_at, 'MM-DD HH:mm')} — {format_price(float(rate.price))}"
