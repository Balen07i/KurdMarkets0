"""Worker — the scheduler/background-job service.

Runs as a SEPARATE Railway service from the Telegram bot (see
railway.toml / Procfile). Owns all scraping, reconciliation, alert
checking, health monitoring, and AI summary generation. The bot process
never imports from `worker` and never talks to providers/scrapers
directly — see core/db.py's `PublishedRate` / Redis cache as the only
handoff point between the two services.
"""
