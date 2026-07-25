"""Centralized application configuration.

All configuration is loaded from environment variables (or a local `.env`
file during development) via `pydantic-settings`. Nothing in this codebase
should call `os.environ` directly outside this module — import `settings`
from here instead, so configuration stays validated and discoverable in one
place.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Values are read from (in order of precedence): real environment
    variables, then a `.env` file in the project root. Railway injects
    `DATABASE_URL` / `REDIS_URL` automatically when Postgres/Redis plugins
    are attached to a service.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Core ---------------------------------------------------------
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    timezone: str = "Asia/Baghdad"

    # --- Telegram -------------------------------------------------------
    telegram_bot_token: str = Field(default="")
    telegram_admin_ids: str = Field(default="")

    # --- Database ---------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/kurdistan_finance"
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/kurdistan_finance"
    )

    # --- Redis --------------------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Reconciliation ------------------------------------------------------
    reconciliation_tolerance_pct: float = 1.5
    reconciliation_min_sources: int = 2
    reconciliation_min_confidence: float = 0.7

    # --- Staleness monitoring ---------------------------------------------
    stale_threshold_minutes: int = 180

    # --- AI summary -----------------------------------------------------
    anthropic_api_key: str = Field(default="")
    ai_summary_model: str = "claude-sonnet-4-6"
    ai_summary_hour: int = 8

    # --- External providers -------------------------------------------------
    coingecko_api_key: str = Field(default="")
    cbi_api_key: str = Field(default="")

    # --- Scheduler intervals (seconds) --------------------------------------
    scrape_interval_currency: int = 300
    scrape_interval_gold: int = 300
    scrape_interval_silver: int = 300
    scrape_interval_fuel: int = 1800
    scrape_interval_crypto: int = 120

    # --- Networking -----------------------------------------------------
    http_timeout_seconds: int = 15
    http_max_retries: int = 3

    # --- Observability --------------------------------------------------
    sentry_dsn: str = Field(default="")

    # --- Domain constants -------------------------------------------------
    # Grams per local "mithqal" (مسقاڵ) as quoted by Iraqi/Kurdistan gold
    # and silver markets. 5.0g is the common convention used by gold shops
    # in Iraq/Kurdistan (distinct from the historical Ottoman mithqal of
    # ~3.5g used elsewhere) — configurable in case this needs correcting
    # for a specific local market convention.
    # TODO: confirm 5.0 against the actual sources once selected.
    mithqal_grams: float = 5.0

    @field_validator("telegram_bot_token")
    @classmethod
    def _warn_if_empty_token(cls, v: str) -> str:
        # Intentionally does not raise: importing `core.config` must never
        # crash (e.g. during `alembic` commands or tests that don't need the
        # bot). Runtime entry points (bot/main.py, worker/main.py) validate
        # required secrets themselves and fail fast with a clear message.
        return v

    @property
    def admin_ids(self) -> list[int]:
        """Parsed list of admin Telegram user IDs."""
        if not self.telegram_admin_ids.strip():
            return []
        return [
            int(chunk.strip())
            for chunk in self.telegram_admin_ids.split(",")
            if chunk.strip()
        ]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance.

    Cached so environment parsing/validation happens exactly once per
    process, and so `get_settings()` can be called cheaply from anywhere
    (including hot paths like per-request handlers).
    """
    return Settings()


# Convenience module-level singleton — most call sites just do:
#   from core.config import settings
settings = get_settings()
