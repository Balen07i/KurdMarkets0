"""Monitoring — admin alerting and health checks.

Covers the four failure modes called out in the product spec: a scraper
fails, data becomes stale, a source changes (i.e. starts consistently
failing to parse), or reconciliation fails (flags a rate for review).
`notifier.py` handles delivery (Telegram DM to configured admins, with
dedup so a repeated failure doesn't spam); `health.py` implements the
staleness/source-health checks the worker runs on a schedule.
"""
