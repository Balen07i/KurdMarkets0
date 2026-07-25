"""Generic "extract one or more numbers from an HTML page" scraping helper.

Local Kurdistan/Iraq market price sites are typically small, simple HTML
pages (not JS-rendered SPAs) that show a table or list of buy/sell rates.
Rather than write near-duplicate BeautifulSoup code in every currency/
gold/silver/fuel provider, this module implements the common "fetch HTML,
select an element, extract a number" pattern once, configured per-source
via CSS selectors.

TODO (ops/admin, before enabling any provider built on this class):
    Kurdistan/Iraq local market price websites and Telegram channels
    change their HTML structure without notice far more often than most
    sites, and several well-known ones (exchange-board style sites,
    local gold-market pages) are not stable/public enough to hardcode a
    URL and CSS selector against sight-unseen in this codebase. Before
    turning on any `HTMLRateScraper`-based provider in production:
      1. Open the source site/channel in a browser and confirm it is
         still live and still shows the expected number.
      2. Fill in `url` and `selector` below (or override `parse()` for
         anything more complex than "one CSS selector, one number").
      3. Add a `Source` row (see alembic/versions/202607240002_seed_assets.py
         for the pattern) with `provider_path` pointing at your subclass.
      4. Start with `trust_weight=1.0` and watch `consecutive_failures`
         in the `sources` table for the first few days.
"""

from __future__ import annotations

import re
from abc import abstractmethod

from selectolax.parser import HTMLParser

from core.exceptions import ScraperParseError
from core.http_client import fetch_text
from providers.base import Provider

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def extract_first_number(text: str) -> float:
    """Pull the first numeric token out of a string like "1,310.50 IQD" or
    "١٬٣١٠" and return it as a float. Strips thousands separators.

    Raises `ScraperParseError` if no number is found — callers should not
    have to guard against `None`/silent zero values.
    """
    normalized = _normalize_digits(text)
    match = _NUMBER_RE.search(normalized)
    if not match:
        raise ScraperParseError(f"No numeric value found in text: {text!r}")
    return float(match.group().replace(",", ""))


_ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_EXTENDED_ARABIC_INDIC_DIGITS = "۰۱۲۳۴۵۶۷۸۹"  # used in Persian/Kurdish Sorani text


def _normalize_digits(text: str) -> str:
    """Convert Arabic-Indic / Extended Arabic-Indic digits (commonly used
    on Iraqi/Iranian sites) to plain ASCII digits, and Arabic-style
    thousands/decimal separator punctuation to their ASCII equivalents,
    before parsing."""
    table = {}
    for i, ch in enumerate(_ARABIC_INDIC_DIGITS):
        table[ord(ch)] = str(i)
    for i, ch in enumerate(_EXTENDED_ARABIC_INDIC_DIGITS):
        table[ord(ch)] = str(i)
    table[0x066C] = ","  # ARABIC THOUSANDS SEPARATOR (٬)
    table[0x066B] = "."  # ARABIC DECIMAL SEPARATOR (٫)
    return text.translate(table)


class HTMLRateScraper(Provider):
    """Base class for "fetch a page, pull a number out of one CSS
    selector" providers. Subclass and set `url` + `selector`, or override
    `parse()` for multi-value pages (e.g. one page listing all 4 gold
    karats)."""

    #: Full URL to fetch. Must be set by subclasses.
    url: str = ""
    #: CSS selector (selectolax/Modest syntax) locating the element whose
    #: text contains the price. Must be set by subclasses unless `parse()`
    #: is overridden.
    selector: str = ""

    async def _fetch_html(self) -> str:
        if not self.url:
            raise ScraperParseError(
                f"{type(self).__name__}.url is not configured — see the TODO "
                f"in providers/currency/local_exchange_scraper.py"
            )
        return await fetch_text(self.url)

    def _extract_single_value(self, html: str) -> float:
        if not self.selector:
            raise ScraperParseError(
                f"{type(self).__name__}.selector is not configured — see the "
                f"TODO in providers/currency/local_exchange_scraper.py"
            )
        tree = HTMLParser(html)
        node = tree.css_first(self.selector)
        if node is None:
            raise ScraperParseError(
                f"Selector {self.selector!r} matched nothing on {self.url} "
                f"— the source page structure may have changed"
            )
        return extract_first_number(node.text(strip=True))

    @abstractmethod
    async def fetch(self):  # pragma: no cover - subclasses implement this
        raise NotImplementedError
