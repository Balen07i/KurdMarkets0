"""Tests for providers/currency/local_exchange_scraper.py's number parsing,
including Arabic-Indic and Extended Arabic-Indic digit normalization
(common on Iraqi/Iranian/Kurdish-language source pages).
"""

from __future__ import annotations

import pytest

from core.exceptions import ScraperParseError
from providers.currency.local_exchange_scraper import extract_first_number


class TestExtractFirstNumber:
    def test_plain_integer(self):
        assert extract_first_number("1310 IQD") == 1310.0

    def test_thousands_separator(self):
        assert extract_first_number("1,310,500") == 1310500.0

    def test_decimal(self):
        assert extract_first_number("1310.50") == 1310.50

    def test_arabic_indic_digits(self):
        # "١٣١٠" is Arabic-Indic for 1310
        assert extract_first_number("١٬٣١٠ دینار") == 1310.0

    def test_extended_arabic_indic_digits(self):
        # "۱۳۱۰" is Extended Arabic-Indic (Persian/Kurdish Sorani) for 1310
        assert extract_first_number("۱۳۱۰ تمەن") == 1310.0

    def test_negative_number(self):
        assert extract_first_number("-2.5%") == -2.5

    def test_no_number_raises(self):
        with pytest.raises(ScraperParseError):
            extract_first_number("no digits here")

    def test_takes_first_number_when_multiple_present(self):
        assert extract_first_number("buy: 1300 sell: 1320") == 1300.0
