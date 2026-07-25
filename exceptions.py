"""Shared exception hierarchy.

Every custom exception in the project should inherit from `AppError` so
top-level handlers (bot error middleware, worker job wrapper) can catch
"our" errors distinctly from unexpected bugs.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all application-raised errors."""


# --- Scraping / providers ---------------------------------------------------


class ScraperError(AppError):
    """A scraper failed to retrieve or parse data from a source."""


class ScraperTimeoutError(ScraperError):
    """A scraper's HTTP request timed out."""


class ScraperParseError(ScraperError):
    """A scraper received a response but could not parse the expected data
    out of it (e.g. the source changed its page/response structure)."""


# --- Reconciliation -----------------------------------------------------


class ReconciliationError(AppError):
    """Raised when reconciliation cannot produce a publishable rate."""


class InsufficientSourcesError(ReconciliationError):
    """Fewer independent sources reported a reading than the configured
    minimum required to reconcile a rate."""


class SourcesDisagreeError(ReconciliationError):
    """Sources disagree beyond the configured tolerance band; the rate has
    been flagged for administrator review instead of being published."""


# --- Data access ---------------------------------------------------------


class NotFoundError(AppError):
    """A requested record does not exist."""


class StaleDataError(AppError):
    """Published data is older than the configured staleness threshold."""


# --- AI ---------------------------------------------------------------------


class AISummaryError(AppError):
    """The AI summary could not be generated."""


class UnverifiedDataAccessError(AppError):
    """Raised if code attempts to let the AI read anything other than
    already-published, verified rates. This should never happen in
    practice — it exists as a hard safety rail, not an expected runtime
    path."""


# --- Configuration --------------------------------------------------------


class ConfigurationError(AppError):
    """Required configuration (e.g. an API key) is missing at runtime."""
