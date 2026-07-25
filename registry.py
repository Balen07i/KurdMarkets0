"""Dynamic provider resolution.

`Source.provider_path` stores a dotted path like
"providers.crypto.coingecko.CoinGeckoProvider". The scheduler never
hardcodes a mapping from source name to provider class — it resolves the
path at runtime via `resolve_provider()`. This is what lets a new source
be turned on purely by inserting a `Source` row (via an Alembic data
migration or an admin command), with no scheduler code change.
"""

from __future__ import annotations

import importlib
from functools import lru_cache

from providers.base import Provider


class ProviderResolutionError(Exception):
    """Raised when a `Source.provider_path` does not resolve to a valid
    `Provider` subclass."""


@lru_cache(maxsize=None)
def resolve_provider_class(provider_path: str) -> type[Provider]:
    """Import and return the Provider class referenced by a dotted path.

    Cached because the same path is resolved repeatedly (once per scrape
    cycle per source) and importlib lookups are not free.
    """
    module_path, _, class_name = provider_path.rpartition(".")
    if not module_path:
        raise ProviderResolutionError(
            f"Invalid provider_path {provider_path!r}: expected 'module.path.ClassName'"
        )

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ProviderResolutionError(
            f"Could not import module {module_path!r} for provider_path {provider_path!r}"
        ) from exc

    provider_class = getattr(module, class_name, None)
    if provider_class is None:
        raise ProviderResolutionError(
            f"Module {module_path!r} has no attribute {class_name!r}"
        )
    if not (isinstance(provider_class, type) and issubclass(provider_class, Provider)):
        raise ProviderResolutionError(
            f"{provider_path!r} does not resolve to a Provider subclass"
        )

    return provider_class


def instantiate_provider(provider_path: str) -> Provider:
    """Resolve and instantiate a fresh Provider for one scrape run."""
    provider_class = resolve_provider_class(provider_path)
    return provider_class()
