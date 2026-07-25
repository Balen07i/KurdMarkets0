"""Central Bank of Iraq (CBI) official USD/IQD exchange rate.

The CBI does not currently expose a public JSON/REST API for exchange
rates, so this reads the published rate off their website.

TODO (before enabling in production):
    1. Verify https://cbi.iq/ still publishes the official rate on the
       page referenced below (CBI has redesigned its site before).
    2. Update `url` / `selector` to match the current markup — open the
       page, inspect the element containing the official USD rate, and
       set a CSS selector that targets it specifically (prefer an
       ID/class over a positional selector so minor layout changes don't
       silently break it).
    3. CBI publishes the rate in IQD per 1 USD as a plain number — confirm
       this is still true and adjust `_parse_value` if the format changes
       (e.g. if they switch to IQD per 100 USD).
"""

from __future__ import annotations

from core.enums import AssetCode
from core.time import now_utc
from providers.base import ProviderReading
from providers.currency.local_exchange_scraper import HTMLRateScraper


class CBIOfficialProvider(HTMLRateScraper):
    """Scrapes the officially published USD/IQD rate from cbi.iq."""

    display_name = "Central Bank of Iraq (Official)"

    # TODO: confirm this is still the correct page for the daily official rate.
    url = "https://cbi.iq/"
    # TODO: replace with a verified selector — this is a placeholder.
    selector = "#official-exchange-rate"

    async def fetch(self) -> list[ProviderReading]:
        html = await self._fetch_html()
        value = self._extract_single_value(html)

        return [
            ProviderReading(
                asset_code=AssetCode.USD_IQD_OFFICIAL,
                value=value,
                currency="iqd",
                observed_at=now_utc(),
            )
        ]
