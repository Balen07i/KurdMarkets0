"""Binance public price provider — the second independent crypto source.

Even though crypto prices have a much clearer "ground truth" than local
IQD market rates, the spec's reconciliation strategy (multiple independent
sources + median + tolerance bands) applies uniformly to every asset
category, so crypto still uses two sources rather than being special-cased
to trust a single API.

Docs: https://binance-docs.github.io/apidocs/spot/en/#symbol-price-ticker
No API key required for public market data endpoints.
"""

from __future__ import annotations

from core.enums import AssetCode
from core.exceptions import ScraperParseError
from core.http_client import fetch_json
from core.logging import get_logger
from core.time import now_utc
from providers.base import Provider, ProviderReading

log = get_logger(__name__)

# Binance trading pair symbol -> our internal AssetCode.
_BINANCE_SYMBOL_MAP: dict[str, AssetCode] = {
    "BTCUSDT": AssetCode.BTC_USD,
    "ETHUSDT": AssetCode.ETH_USD,
    "BNBUSDT": AssetCode.BNB_USD,
    "SOLUSDT": AssetCode.SOL_USD,
    "XRPUSDT": AssetCode.XRP_USD,
}

_URL = "https://api.binance.com/api/v3/ticker/price"


class BinanceProvider(Provider):
    """Single source covering all five tracked crypto assets in one call.

    USDT is treated as 1:1 with USD for this bot's purposes — the
    difference is far smaller than the reconciliation tolerance band for
    any of these assets.
    """

    display_name = "Binance API"

    async def fetch(self) -> list[ProviderReading]:
        symbols_param = "[" + ",".join(f'"{s}"' for s in _BINANCE_SYMBOL_MAP) + "]"
        url = f"{_URL}?symbols={symbols_param}"

        data = await fetch_json(url)

        if not isinstance(data, list):
            raise ScraperParseError(f"Unexpected Binance response shape: {data!r}")

        observed_at = now_utc()
        by_symbol = {entry["symbol"]: entry for entry in data if "symbol" in entry}

        readings: list[ProviderReading] = []
        for symbol, asset_code in _BINANCE_SYMBOL_MAP.items():
            entry = by_symbol.get(symbol)
            if not entry or "price" not in entry:
                raise ScraperParseError(f"Binance response missing price for {symbol!r}")
            readings.append(
                ProviderReading(
                    asset_code=asset_code,
                    value=float(entry["price"]),
                    currency="usd",
                    observed_at=observed_at,
                    raw_payload={symbol: entry},
                )
            )

        if not readings:
            raise ScraperParseError("Binance response contained no usable prices")

        return readings
