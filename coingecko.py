"""CoinGecko crypto price provider.

Fully functional against CoinGecko's public `/simple/price` endpoint — no
API key is required at the request volumes this bot needs (one request
covering all 5 coins every `SCRAPE_INTERVAL_CRYPTO` seconds). If
`COINGECKO_API_KEY` is set, it is sent as a Pro-API header automatically to
raise rate limits.

Docs: https://www.coingecko.com/en/api/documentation
"""

from __future__ import annotations

from core.config import settings
from core.enums import AssetCode
from core.exceptions import ScraperParseError
from core.http_client import fetch_json
from core.logging import get_logger
from core.time import now_utc
from providers.base import Provider, ProviderReading

log = get_logger(__name__)

# CoinGecko "id" -> our internal AssetCode.
_COINGECKO_ID_MAP: dict[str, AssetCode] = {
    "bitcoin": AssetCode.BTC_USD,
    "ethereum": AssetCode.ETH_USD,
    "binancecoin": AssetCode.BNB_USD,
    "solana": AssetCode.SOL_USD,
    "ripple": AssetCode.XRP_USD,
}

_BASE_URL = "https://api.coingecko.com/api/v3/simple/price"
_PRO_BASE_URL = "https://pro-api.coingecko.com/api/v3/simple/price"


class CoinGeckoProvider(Provider):
    """Single source covering all five tracked crypto assets in one call."""

    display_name = "CoinGecko API"

    async def fetch(self) -> list[ProviderReading]:
        ids = ",".join(_COINGECKO_ID_MAP.keys())
        headers = {}
        base_url = _BASE_URL
        if settings.coingecko_api_key:
            base_url = _PRO_BASE_URL
            headers["x-cg-pro-api-key"] = settings.coingecko_api_key

        url = f"{base_url}?ids={ids}&vs_currencies=usd"

        data = await fetch_json(url, headers=headers)

        observed_at = now_utc()
        readings: list[ProviderReading] = []
        for coingecko_id, asset_code in _COINGECKO_ID_MAP.items():
            entry = data.get(coingecko_id)
            if not entry or "usd" not in entry:
                raise ScraperParseError(
                    f"CoinGecko response missing 'usd' price for {coingecko_id!r}: {data}"
                )
            readings.append(
                ProviderReading(
                    asset_code=asset_code,
                    value=float(entry["usd"]),
                    currency="usd",
                    observed_at=observed_at,
                    raw_payload={coingecko_id: entry},
                )
            )

        if not readings:
            raise ScraperParseError("CoinGecko response contained no usable prices")

        return readings
