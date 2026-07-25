"""Tests for providers/registry.py's dynamic provider_path resolution."""

from __future__ import annotations

import pytest

from providers.registry import (
    ProviderResolutionError,
    instantiate_provider,
    resolve_provider_class,
)


class TestResolveProviderClass:
    def test_resolves_real_provider(self):
        cls = resolve_provider_class("providers.crypto.coingecko.CoinGeckoProvider")
        from providers.crypto.coingecko import CoinGeckoProvider

        assert cls is CoinGeckoProvider

    def test_missing_module_raises(self):
        with pytest.raises(ProviderResolutionError):
            resolve_provider_class("providers.nonexistent.module.SomeProvider")

    def test_missing_class_raises(self):
        with pytest.raises(ProviderResolutionError):
            resolve_provider_class("providers.crypto.coingecko.NotARealClass")

    def test_malformed_path_raises(self):
        with pytest.raises(ProviderResolutionError):
            resolve_provider_class("NoDotsAtAll")

    def test_non_provider_class_raises(self):
        with pytest.raises(ProviderResolutionError):
            # core.enums.AssetCode exists but is not a Provider subclass.
            resolve_provider_class("core.enums.AssetCode")


class TestInstantiateProvider:
    def test_instantiates_fresh_instance(self):
        instance = instantiate_provider("providers.crypto.binance.BinanceProvider")
        from providers.crypto.binance import BinanceProvider

        assert isinstance(instance, BinanceProvider)
