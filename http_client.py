"""Shared HTTP client factory for all scrapers/providers.

Centralizing this means every scraper gets the same timeout, retry, and
User-Agent policy by default instead of each one reinventing (and
inevitably getting slightly wrong) its own `httpx.Client` setup.
"""

from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.config import settings
from core.exceptions import ScraperError, ScraperTimeoutError
from core.logging import get_logger

log = get_logger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 "
        "KurdistanFinanceBot/1.0 (+https://github.com/)"
    ),
    "Accept-Language": "en-US,en;q=0.9,ku;q=0.8,ar;q=0.7",
}


def build_http_client(**overrides: object) -> httpx.AsyncClient:
    """Construct a new AsyncClient with the project's default policy.

    Each scraper should create its own client (via `async with
    build_http_client() as client:`) rather than sharing one globally —
    scrapers run infrequently (minutes apart) so connection reuse isn't
    worth the complexity of a shared long-lived client with unclear
    lifecycle ownership.
    """
    kwargs: dict[str, object] = {
        "timeout": settings.http_timeout_seconds,
        "headers": DEFAULT_HEADERS,
        "follow_redirects": True,
    }
    kwargs.update(overrides)
    return httpx.AsyncClient(**kwargs)  # type: ignore[arg-type]


def retry_on_transient_error():
    """Tenacity decorator applying the project's standard scraper retry
    policy: exponential backoff, bounded attempts, only on transient
    network errors (never retries on parse errors — those are a bug in
    the scraper, not a transient failure)."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(settings.http_max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    )


async def fetch_text(url: str, **kwargs: object) -> str:
    """Convenience helper: GET a URL and return response text, wrapping
    httpx errors in our own exception types so scrapers only need to
    catch `ScraperError`."""

    @retry_on_transient_error()
    async def _do_fetch() -> str:
        async with build_http_client() as client:
            try:
                response = await client.get(url, **kwargs)  # type: ignore[arg-type]
                response.raise_for_status()
                return response.text
            except httpx.TimeoutException as exc:
                raise ScraperTimeoutError(f"Timed out fetching {url}") from exc
            except httpx.HTTPStatusError as exc:
                raise ScraperError(
                    f"HTTP {exc.response.status_code} fetching {url}"
                ) from exc
            except httpx.TransportError as exc:
                raise ScraperError(f"Transport error fetching {url}: {exc}") from exc

    return await _do_fetch()


async def fetch_json(url: str, **kwargs: object) -> dict:
    """Convenience helper: GET a URL and return parsed JSON."""

    @retry_on_transient_error()
    async def _do_fetch() -> dict:
        async with build_http_client() as client:
            try:
                response = await client.get(url, **kwargs)  # type: ignore[arg-type]
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as exc:
                raise ScraperTimeoutError(f"Timed out fetching {url}") from exc
            except httpx.HTTPStatusError as exc:
                raise ScraperError(
                    f"HTTP {exc.response.status_code} fetching {url}"
                ) from exc
            except httpx.TransportError as exc:
                raise ScraperError(f"Transport error fetching {url}: {exc}") from exc

    return await _do_fetch()
