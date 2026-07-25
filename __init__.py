"""Telegram bot — the user-facing service.

Runs as its own Railway service (see railway.toml). The bot NEVER
scrapes, NEVER talks to providers, and NEVER writes RawReading/
PublishedRate rows — it only reads verified data via `history/rates.py`
and `history/ai_summary.py`, and writes its own tables (`users`,
`alerts`).
"""
