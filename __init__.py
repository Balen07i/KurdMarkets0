"""Reconciliation — turns multiple independent RawReadings into exactly one
verified PublishedRate (or flags them for admin review).

This is the ONLY code path allowed to create `PublishedRate` rows. See
`engine.py` for the verification strategy (weighted median, tolerance
bands, confidence scoring) and `publisher.py` for the persistence +
alert-triggering side effects of a successful publication.
"""
