"""Independent Kurdistan fuel price source #2 — must be a different
operator/site than site_one.py. See the checklist in
providers/currency/local_market_site_one.py.
"""

from __future__ import annotations

from selectolax.parser import HTMLParser

from core.enums import AssetCode
from core.exceptions import ScraperParseError
from core.logging import get_logger
from core.time import now_utc
from providers.base import ProviderReading
from providers.currency.local_exchange_scraper import (
    HTMLRateScraper,
    extract_first_number,
)

log = get_logger(__name__)

# TODO: map this (different) source's exact labels to our AssetCode.
_LABEL_TO_ASSET: dict[str, AssetCode] = {
    "بەنزینی خۆڕو": AssetCode.FUEL_PETROL,
    "گازۆیل": AssetCode.FUEL_DIESEL,
    "گازی ماڵەوە": AssetCode.FUEL_GAS,
}


class FuelSiteTwoProvider(HTMLRateScraper):
    display_name = "Kurdistan Fuel Prices — Source 2"

    # TODO: replace with a verified, real, independent source URL.
    url = "https://example-fuel-source-two.invalid/prices"

    # TODO: replace with real selectors matching the chosen source's markup.
    _ROW_SELECTOR = "div.fuel-row"
    _LABEL_SELECTOR = "span.fuel-name"
    _VALUE_SELECTOR = "span.fuel-price"

    async def fetch(self) -> list[ProviderReading]:
        html = await self._fetch_html()
        tree = HTMLParser(html)
        rows = tree.css(self._ROW_SELECTOR)
        if not rows:
            raise ScraperParseError(f"No rows matched {self._ROW_SELECTOR!r} on {self.url}")

        observed_at = now_utc()
        readings: list[ProviderReading] = []

        for row in rows:
            label_node = row.css_first(self._LABEL_SELECTOR)
            value_node = row.css_first(self._VALUE_SELECTOR)
            if label_node is None or value_node is None:
                continue

            label = label_node.text(strip=True)
            asset_code = _LABEL_TO_ASSET.get(label)
            if asset_code is None:
                continue

            try:
                value = extract_first_number(value_node.text(strip=True))
            except ScraperParseError:
                log.warning("fuel_site_two_row_unparsable", label=label)
                continue

            readings.append(
                ProviderReading(
                    asset_code=asset_code,
                    value=value,
                    currency="iqd",
                    observed_at=observed_at,
                )
            )

        if not readings:
            raise ScraperParseError(
                f"Matched {len(rows)} row(s) but extracted zero fuel readings "
                f"— check _LABEL_TO_ASSET mapping"
            )

        return readings
