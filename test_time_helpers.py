"""Tests for core/time.py."""

from __future__ import annotations

from datetime import datetime, timezone

from freezegun import freeze_time

from core.time import minutes_since, now_utc, today_local


class TestNowUtc:
    @freeze_time("2026-07-24 12:00:00")
    def test_returns_current_utc_time(self):
        result = now_utc()
        assert result.year == 2026
        assert result.month == 7
        assert result.day == 24


class TestTodayLocal:
    @freeze_time("2026-07-24 23:30:00", tz_offset=0)
    def test_returns_a_date(self):
        result = today_local()
        assert result.year == 2026


class TestMinutesSince:
    @freeze_time("2026-07-24 12:30:00")
    def test_computes_elapsed_minutes(self):
        past = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)
        elapsed = minutes_since(past)
        assert 29.0 <= elapsed <= 31.0

    @freeze_time("2026-07-24 12:00:00")
    def test_zero_elapsed_for_current_moment(self):
        now = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)
        elapsed = minutes_since(now)
        assert elapsed < 0.01
