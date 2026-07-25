"""Timezone-aware datetime helpers.

All "current time" reads in the codebase should go through `now_utc()` or
`now_local()` here rather than calling `datetime.now()` directly, so
behavior is consistent and testable (see tests/conftest.py, which freezes
time using these entry points).
"""

from __future__ import annotations

from datetime import date, datetime

import pendulum

from core.config import settings


def now_utc() -> datetime:
    """Current time, timezone-aware, in UTC. Use this for anything stored
    in the database (all DateTime columns are `timezone=True`)."""
    return pendulum.now("UTC")


def now_local() -> datetime:
    """Current time in the configured application timezone (default
    Asia/Baghdad). Use this for anything shown to users or used in
    scheduling decisions (e.g. "has the 08:00 summary run yet today")."""
    return pendulum.now(settings.timezone)


def today_local() -> date:
    """Local calendar date — used as the natural key for the daily AI
    summary (`AISummary.summary_date`)."""
    return now_local().date()


def to_local(dt: datetime) -> datetime:
    """Convert an arbitrary (assumed UTC-aware) datetime to local display
    time."""
    return pendulum.instance(dt).in_timezone(settings.timezone)


def format_local(dt: datetime, fmt: str = "YYYY-MM-DD HH:mm") -> str:
    """Format a datetime in local time for user-facing display."""
    return to_local(dt).format(fmt)


def minutes_since(dt: datetime) -> float:
    """Minutes elapsed between `dt` and now — used by staleness checks."""
    return (now_utc() - pendulum.instance(dt)).total_minutes()
