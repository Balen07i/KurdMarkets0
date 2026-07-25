"""Independent local silver market source #2 — must be a different
operator/site than local_market_site_one.py. See the checklist in
providers/currency/local_market_site_one.py.
"""

from __future__ import annotations

from core.enums import AssetCode
from core.time import now_utc
from providers.base import ProviderReading
from providers.currency.local_exchange_scraper import HTMLRateScraper


class SilverLocalMarketSiteTwoProvider(HTMLRateScraper):
    display_name = "Local Silver Market — Source 2"

    # TODO: replace with a verified, real, independent source URL.
    url = "https://example-silver-source-two.invalid/rates"
    # TODO: replace with a verified selector.
    selector = ".silver-rate .value"

    async def fetch(self) -> list[ProviderReading]:
        html = await self._fetch_html()
        value = self._extract_single_value(html)
        return [
            ProviderReading(
                asset_code=AssetCode.SILVER,
                value=value,
                currency="iqd",
                observed_at=now_utc(),
            )
        ]
