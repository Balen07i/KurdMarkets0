"""Tests for bot/formatting.py — pure string formatting, no I/O."""

from __future__ import annotations

from bot.formatting import format_change, format_price


class TestFormatPrice:
    def test_integer_value_no_decimals(self):
        assert format_price(1310.0) == "1,310"

    def test_decimal_value_two_places(self):
        assert format_price(1310.5) == "1,310.50"

    def test_large_number_thousands_separators(self):
        assert format_price(1234567.0) == "1,234,567"

    def test_small_crypto_fraction(self):
        assert format_price(0.5) == "0.50"


class TestFormatChange:
    def test_none_returns_placeholder(self):
        assert format_change(None, None) == "—"

    def test_positive_change_has_up_arrow_and_sign(self):
        result = format_change(1.25, 15.0)
        assert "🔺" in result
        assert "+1.25%" in result

    def test_negative_change_has_down_arrow(self):
        result = format_change(-2.5, -30.0)
        assert "🔻" in result
        assert "-2.50%" in result

    def test_zero_change_has_flat_arrow(self):
        result = format_change(0.0, 0.0)
        assert "➖" in result
