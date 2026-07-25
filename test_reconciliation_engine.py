"""Tests for reconciliation/engine.py — the core verification logic.

These are pure unit tests: no database, no network. `reconcile()` is
DB-agnostic by design specifically so it can be exhaustively tested this
way (see the module docstring in reconciliation/engine.py).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from core.enums import PublicationStatus
from reconciliation.engine import CandidateReading, reconcile, weighted_median


def _reading(value: float, trust_weight: float = 1.0, source_id: uuid.UUID | None = None) -> CandidateReading:
    return CandidateReading(
        reading_id=uuid.uuid4(),
        source_id=source_id or uuid.uuid4(),
        source_name="test-source",
        trust_weight=trust_weight,
        value=value,
        observed_at=datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc),
    )


class TestWeightedMedian:
    def test_odd_count_equal_weights(self):
        assert weighted_median([(1.0, 1.0), (2.0, 1.0), (3.0, 1.0)]) == 2.0

    def test_single_value(self):
        assert weighted_median([(42.0, 1.0)]) == 42.0

    def test_weighted_toward_heavier_source(self):
        # A much-heavier-weighted low value should pull the "median" down.
        result = weighted_median([(10.0, 10.0), (100.0, 1.0)])
        assert result == 10.0

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            weighted_median([])


class TestReconcile:
    def test_agreeing_sources_publish(self):
        readings = [_reading(1310.0), _reading(1312.0), _reading(1311.0)]
        result = reconcile(readings, min_sources=2, tolerance_pct=1.5, min_confidence=0.5)

        assert result.status == PublicationStatus.PUBLISHED
        assert result.price is not None
        assert 1310.0 <= result.price <= 1312.0
        assert len(result.used_reading_ids) == 3
        assert not result.rejected_reading_ids

    def test_insufficient_sources_flags_for_review(self):
        readings = [_reading(1310.0)]
        result = reconcile(readings, min_sources=2, tolerance_pct=1.5, min_confidence=0.5)

        assert result.status == PublicationStatus.PENDING_REVIEW
        assert result.price is None
        assert "1 independent source" in result.review_reason

    def test_disagreeing_sources_flag_for_review(self):
        # 1310 vs 1500 is a ~14% deviation, far beyond a 1.5% tolerance.
        readings = [_reading(1310.0), _reading(1500.0)]
        result = reconcile(readings, min_sources=2, tolerance_pct=1.5, min_confidence=0.5)

        assert result.status == PublicationStatus.PENDING_REVIEW
        assert result.price is None
        assert result.review_reason is not None

    def test_single_outlier_rejected_others_published(self):
        # Three sources agree closely, one is a clear outlier.
        readings = [
            _reading(1310.0),
            _reading(1311.0),
            _reading(1312.0),
            _reading(1600.0),  # outlier
        ]
        result = reconcile(readings, min_sources=2, tolerance_pct=1.5, min_confidence=0.5)

        assert result.status == PublicationStatus.PUBLISHED
        assert len(result.used_reading_ids) == 3
        assert len(result.rejected_reading_ids) == 1

    def test_low_confidence_flags_for_review_even_with_a_price(self):
        # Exactly at the edge of tolerance for 2 sources -> low agreement
        # score; with a very high min_confidence this should be flagged.
        readings = [_reading(1000.0), _reading(1014.9)]  # ~1.49% apart
        result = reconcile(readings, min_sources=2, tolerance_pct=1.5, min_confidence=0.99)

        assert result.status == PublicationStatus.PENDING_REVIEW
        assert result.price is not None  # a candidate was computable
        assert result.confidence_score < 0.99

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            reconcile([])

    def test_confidence_score_is_between_zero_and_one(self):
        readings = [_reading(100.0), _reading(100.5), _reading(99.5)]
        result = reconcile(readings, min_sources=2, tolerance_pct=2.0, min_confidence=0.0)
        assert 0.0 <= result.confidence_score <= 1.0

    def test_uses_configured_defaults_when_not_overridden(self):
        # Should not raise even without explicit kwargs — falls back to
        # core.config.settings values.
        readings = [_reading(1.0), _reading(1.0)]
        result = reconcile(readings)
        assert result.status in (PublicationStatus.PUBLISHED, PublicationStatus.PENDING_REVIEW)
