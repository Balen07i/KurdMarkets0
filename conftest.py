"""Shared pytest fixtures.

Deliberately does NOT spin up a real Postgres/Redis — the test suite here
covers pure business logic (reconciliation, formatting, parsing, provider
resolution) that needs no I/O. Tests exercising the DB layer belong in a
separate integration suite run against a real (e.g. Dockerized or Railway
staging) Postgres — see docs/DEPLOYMENT.md for how CI is expected to wire
that up; it's intentionally not part of this fast unit-test suite.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

# Ensure `core.config.Settings()` never tries to read a real .env file
# that might exist on a dev machine and pull in unexpected values —
# tests should be deterministic regardless of the local environment.
os.environ.setdefault("APP_ENV", "development")


@pytest.fixture
def make_reading_id():
    """Factory for readable, deterministic-looking UUIDs in test data."""

    def _make() -> uuid.UUID:
        return uuid.uuid4()

    return _make


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)
