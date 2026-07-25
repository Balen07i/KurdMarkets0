"""Independent Kurdistan fuel price source #1.

Returns petrol/diesel/cooking-gas prices. TODO: see the checklist in
providers/currency/local_market_site_one.py — pick a real source (e.g. a
KRG Ministry of Natural Resources announcement page, or a tracked fuel
station operator's published price list) and verify selectors.
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

# TODO: map this source's exact labels to our AssetCode.
_LABEL_TO_ASSET: dict[str, AssetCode] = {
    "petrol": AssetCode.FUEL_PETROL,
    "بەنزین": AssetCode.FUEL_PETROL,
    "diesel": AssetCode.FUEL_DIESEL,
    "گازۆیل": AssetCode.FUEL_DIESEL,
    "gas": AssetCode.FUEL_GAS,
    "گاز": AssetCode.FUEL_GAS,
}


class FuelSiteOneProvider(HTMLRateScraper):
    display_name = "Kurdistan Fuel Prices — Source 1"

    # TODO: replace with a verified, real source URL.
    url = "https://example-fuel-source-one.invalid/prices"

    # TODO: replace with real selectors matching the chosen source's markup.
    _ROW_SELECTOR = "table.fuel-prices tr"
    _LABEL_SELECTOR = "td.fuel-type"
    _VALUE_SELECTOR = "td.price-per-liter"

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

            label = label_node.text(strip=True).lower()
            asset_code = _LABEL_TO_ASSET.get(label)
            if asset_code is None:
                continue

            try:
                value = extract_first_number(value_node.text(strip=True))
            except ScraperParseError:
                log.warning("fuel_site_one_row_unparsable", label=label)
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
