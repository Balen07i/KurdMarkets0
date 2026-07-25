"""Tests for core/config.py's Settings parsing helpers."""

from __future__ import annotations

from core.config import Settings


class TestAdminIds:
    def test_empty_string_returns_empty_list(self):
        settings = Settings(telegram_admin_ids="")
        assert settings.admin_ids == []

    def test_single_id(self):
        settings = Settings(telegram_admin_ids="123456789")
        assert settings.admin_ids == [123456789]

    def test_multiple_ids_comma_separated(self):
        settings = Settings(telegram_admin_ids="111, 222,333")
        assert settings.admin_ids == [111, 222, 333]

    def test_trailing_comma_ignored(self):
        settings = Settings(telegram_admin_ids="111,222,")
        assert settings.admin_ids == [111, 222]


class TestIsProduction:
    def test_development_is_not_production(self):
        settings = Settings(app_env="development")
        assert settings.is_production is False

    def test_production_flag(self):
        settings = Settings(app_env="production")
        assert settings.is_production is True


class TestDefaults:
    def test_reconciliation_defaults_are_sane(self):
        settings = Settings()
        assert settings.reconciliation_min_sources >= 1
        assert 0 < settings.reconciliation_tolerance_pct < 100
        assert 0 <= settings.reconciliation_min_confidence <= 1

    def test_mithqal_grams_positive(self):
        settings = Settings()
        assert settings.mithqal_grams > 0
