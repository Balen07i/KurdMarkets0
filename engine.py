"""Core reconciliation logic: verify multiple independent readings and
produce either a publishable rate or a documented reason it can't be
published automatically.

Deliberately pure/synchronous and DB-agnostic (operates on plain
dataclasses, not ORM objects) so it can be unit-tested with no database at
all — see tests/test_reconciliation.py.
"""

from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass
from datetime import datetime

from core.config import settings
from core.enums import PublicationStatus
from core.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CandidateReading:
    """A minimal, DB-agnostic view of one RawReading fed into
    reconciliation. The worker's scrape/reconcile job maps `RawReading`
    ORM rows to these before calling `reconcile()`."""

    reading_id: uuid.UUID
    source_id: uuid.UUID
    source_name: str
    trust_weight: float
    value: float
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """The outcome of attempting to reconcile one asset's pending readings."""

    status: PublicationStatus
    price: float | None
    confidence_score: float
    used_reading_ids: list[uuid.UUID]
    rejected_reading_ids: list[uuid.UUID]
    rejection_reasons: dict[uuid.UUID, str]
    review_reason: str | None
    meta: dict


def weighted_median(values_and_weights: list[tuple[float, float]]) -> float:
    """Weighted median: the value at which the cumulative weight first
    reaches half the total weight. Falls back to the plain median when all
    weights are equal (the common case at launch, before any source's
    `trust_weight` has been manually tuned)."""
    if not values_and_weights:
        raise ValueError("weighted_median requires at least one value")

    sorted_pairs = sorted(values_and_weights, key=lambda pair: pair[0])
    total_weight = sum(weight for _, weight in sorted_pairs)
    if total_weight <= 0:
        raise ValueError("total weight must be positive")

    cumulative = 0.0
    half = total_weight / 2.0
    for value, weight in sorted_pairs:
        cumulative += weight
        if cumulative >= half:
            return value

    return sorted_pairs[-1][0]  # pragma: no cover - unreachable in practice


def reconcile(
    readings: list[CandidateReading],
    *,
    min_sources: int | None = None,
    tolerance_pct: float | None = None,
    min_confidence: float | None = None,
) -> ReconciliationResult:
    """Reconcile a batch of independent readings for ONE asset at ONE
    scrape cycle into a single verified value, or flag them for review.

    Verification strategy (per the product spec):
      1. Require at least `min_sources` independent sources.
      2. Compute the (trust-weighted) median as the candidate value.
      3. Reject any reading that deviates from the median by more than
         `tolerance_pct`; if that leaves fewer than `min_sources` readings,
         the whole batch is flagged for review rather than published.
      4. Compute a confidence score from source count and agreement.
      5. If confidence is below `min_confidence`, flag for review even
         though a value was computable — better to under-publish than to
         publish something we're not confident in.

    Never raises for "couldn't reconcile" cases — those are represented in
    the returned `ReconciliationResult.status`. Only raises on genuine
    programming errors (e.g. empty input).
    """
    if not readings:
        raise ValueError("reconcile() requires at least one reading")

    min_sources = min_sources if min_sources is not None else settings.reconciliation_min_sources
    tolerance_pct = (
        tolerance_pct if tolerance_pct is not None else settings.reconciliation_tolerance_pct
    )
    min_confidence = (
        min_confidence if min_confidence is not None else settings.reconciliation_min_confidence
    )

    all_ids = [r.reading_id for r in readings]

    # --- Step 1: minimum source count -------------------------------------
    distinct_sources = {r.source_id for r in readings}
    if len(distinct_sources) < min_sources:
        reason = (
            f"Only {len(distinct_sources)} independent source(s) reported "
            f"(minimum required: {min_sources})"
        )
        log.warning("reconciliation_insufficient_sources", sources=len(distinct_sources), required=min_sources)
        return ReconciliationResult(
            status=PublicationStatus.PENDING_REVIEW,
            price=None,
            confidence_score=0.0,
            used_reading_ids=[],
            rejected_reading_ids=all_ids,
            rejection_reasons={},
            review_reason=reason,
            meta={"distinct_sources": len(distinct_sources), "min_sources": min_sources},
        )

    # --- Step 2: candidate value via weighted median ------------------------
    candidate = weighted_median([(r.value, r.trust_weight) for r in readings])

    # --- Step 3: tolerance-band outlier rejection ---------------------------
    used: list[CandidateReading] = []
    rejected: list[CandidateReading] = []
    rejection_reasons: dict[uuid.UUID, str] = {}

    for r in readings:
        deviation_pct = abs(r.value - candidate) / candidate * 100 if candidate else 0.0
        if deviation_pct > tolerance_pct:
            rejected.append(r)
            rejection_reasons[r.reading_id] = (
                f"deviates {deviation_pct:.2f}% from median {candidate:.4f} "
                f"(tolerance {tolerance_pct:.2f}%)"
            )
        else:
            used.append(r)

    used_distinct_sources = {r.source_id for r in used}
    if len(used_distinct_sources) < min_sources:
        reason = (
            f"Sources disagree beyond tolerance: only {len(used_distinct_sources)} of "
            f"{len(distinct_sources)} source(s) fell within {tolerance_pct:.2f}% of the median"
        )
        log.warning(
            "reconciliation_sources_disagree",
            used_sources=len(used_distinct_sources),
            total_sources=len(distinct_sources),
            tolerance_pct=tolerance_pct,
        )
        return ReconciliationResult(
            status=PublicationStatus.PENDING_REVIEW,
            price=None,
            confidence_score=0.0,
            used_reading_ids=[],
            rejected_reading_ids=all_ids,
            rejection_reasons=rejection_reasons,
            review_reason=reason,
            meta={
                "candidate_median": candidate,
                "values": [r.value for r in readings],
                "tolerance_pct": tolerance_pct,
            },
        )

    # Recompute the final value from only the in-tolerance readings, so a
    # single wide outlier doesn't skew the published price even slightly.
    final_price = weighted_median([(r.value, r.trust_weight) for r in used])

    # --- Step 4: confidence score --------------------------------------
    confidence_score = _compute_confidence(used, rejected, tolerance_pct)

    meta = {
        "final_price": final_price,
        "used_values": [r.value for r in used],
        "rejected_values": [r.value for r in rejected],
        "source_count": len(used_distinct_sources),
        "tolerance_pct": tolerance_pct,
    }

    # --- Step 5: confidence threshold ----------------------------------
    if confidence_score < min_confidence:
        reason = (
            f"Confidence score {confidence_score:.2f} is below the minimum "
            f"required {min_confidence:.2f}"
        )
        log.warning("reconciliation_low_confidence", confidence=confidence_score, required=min_confidence)
        return ReconciliationResult(
            status=PublicationStatus.PENDING_REVIEW,
            price=final_price,
            confidence_score=confidence_score,
            used_reading_ids=[r.reading_id for r in used],
            rejected_reading_ids=[r.reading_id for r in rejected],
            rejection_reasons=rejection_reasons,
            review_reason=reason,
            meta=meta,
        )

    return ReconciliationResult(
        status=PublicationStatus.PUBLISHED,
        price=final_price,
        confidence_score=confidence_score,
        used_reading_ids=[r.reading_id for r in used],
        rejected_reading_ids=[r.reading_id for r in rejected],
        rejection_reasons=rejection_reasons,
        review_reason=None,
        meta=meta,
    )


def _compute_confidence(
    used: list[CandidateReading],
    rejected: list[CandidateReading],
    tolerance_pct: float,
) -> float:
    """Confidence blends two signals, weighted equally:

      - Agreement: how tightly the used readings cluster (relative to the
        tolerance band — perfect agreement scores 1.0, readings right at
        the tolerance edge score ~0.0).
      - Coverage: how many of all reporting sources were actually used
        (rejecting outliers lowers this).

    This is a deliberately simple, explainable formula (not a black box)
    since confidence scores are shown to admins reviewing flagged rates —
    see docs/ARCHITECTURE.md for the rationale and tuning history.
    """
    if not used:
        return 0.0

    values = [r.value for r in used]
    mean_value = statistics.fmean(values)
    if mean_value == 0 or len(values) == 1:
        agreement = 1.0 if len(values) == 1 else 0.0
    else:
        spread_pct = (max(values) - min(values)) / mean_value * 100
        agreement = max(0.0, 1.0 - (spread_pct / tolerance_pct)) if tolerance_pct > 0 else 1.0

    total = len(used) + len(rejected)
    coverage = len(used) / total if total else 0.0

    return round(0.5 * agreement + 0.5 * coverage, 4)
