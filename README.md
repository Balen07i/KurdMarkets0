# Kurdistan Finance Bot

A production-quality Telegram bot delivering verified financial
intelligence — currencies, gold, silver, fuel, and crypto — for Iraq and
the Kurdistan Region, with a daily AI-generated Kurdish market summary.

The bot never guesses. Every number it shows has passed through a
multi-source verification pipeline (see [Architecture](#architecture)
below) before it's ever displayed to a user or read by the AI summary.

## Features

- 💵 **Currencies** — USD/IQD (official + local market), EUR/IQD,
  TRY/IQD, IRT/IQD — each with current price, daily change, history, and
  price alerts.
- 🥇 **Gold** — 18K/21K/22K/24K per-mithqal and per-gram prices, plus Gold
  Lira.
- 🥈 **Silver** — per-mithqal and per-gram.
- ⛽ **Fuel** — petrol, diesel, cooking gas.
- ₿ **Crypto** — BTC, ETH, BNB, SOL, XRP.
- 📊 **AI Daily Summary** — one Kurdish-language market recap generated
  once per day from verified data and served identically to every user.
- 🔔 **Price alerts** — "notify me when X crosses Y".
- 🛡️ **Admin review** — rates reconciliation can't auto-verify are
  queued for a human admin to approve or reject, never silently guessed.

## Architecture at a glance

```
Scrapers (providers/) → RawReading (raw_readings table, permanent audit log)
        ↓
Reconciliation (median + tolerance + confidence) (reconciliation/)
        ↓
PublishedRate (published_rates table — the ONLY thing the bot/AI ever reads)
        ↓
Redis cache (fast bot reads) ──→ Telegram Bot (bot/) ──→ Users
```

Two separate services, two separate Railway deployments:

- **`worker`** — scrapes, reconciles, monitors, generates the AI summary.
  Never talks to Telegram users directly (except sending admin alerts).
- **`bot`** — the user-facing Telegram bot. Never scrapes, never talks to
  providers, never writes `PublishedRate` rows. Reads only through
  `history/rates.py` and `history/ai_summary.py`.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design
rationale, and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for how to deploy
both services to Railway.

## Project layout

```
bot/              Telegram bot (aiogram) — handlers, keyboards, middlewares
worker/           Scheduler/background jobs (APScheduler) — scrape, reconcile, alerts, summary, health
core/             Shared: config, db, redis, logging, exceptions, enums, models
providers/        One module per data source — the "plugin" layer for scrapers/APIs
reconciliation/   Multi-source verification engine + publisher
monitoring/       Admin alerting + health checks
history/          Read-only verified-data queries + AI summary generation
alembic/          Database migrations (schema + seed data)
tests/            Unit tests (pure logic — no DB/network required)
docs/             Architecture and deployment documentation
```

## Getting started (local development)

### Prerequisites

- Python 3.11+
- Docker (for local Postgres/Redis via `docker-compose.yml`), or your own
  Postgres 14+ and Redis 6+

### Setup

```bash
cp .env.example .env
# Fill in at minimum: TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_IDS, ANTHROPIC_API_KEY

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d postgres redis
alembic upgrade head          # creates schema + seeds assets/sources

# Two separate processes, exactly like production:
python -m worker.main &
python -m bot.main
```

### Running tests

```bash
pytest
```

The included test suite is intentionally pure-logic (reconciliation
engine, number parsing, formatting, provider resolution, config parsing)
so it runs fast with no external services. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#testing-strategy) for how to
extend it with a DB-backed integration suite.

### Adding a new asset

Because every asset category behaves like a plugin, adding one is a data
change, not a rewrite:

1. Add a value to `AssetCode` in `core/enums.py`.
2. Add a row to `SEED_ASSETS` in a new Alembic data migration (see
   `alembic/versions/202607240002_seed_assets.py` for the pattern).
3. Write a `Provider` subclass in `providers/<category>/` implementing
   `fetch()`.
4. Add a `Source` row (same migration pattern as
   `202607240003_seed_sources.py`) pointing at your provider's dotted
   path.

Nothing in `bot/`, `worker/`, or `reconciliation/` needs to change.

### Configuring real data sources

The currency/gold/silver/fuel scrapers ship with the full scraping
machinery (HTTP fetching, retry policy, HTML parsing, Arabic/Kurdish digit
normalization) but placeholder URLs/selectors — Kurdistan/Iraq local
market sites are not stable or public enough to hardcode sight-unseen.
**Every provider file with a `TODO` at the top needs a real source picked
and its selectors verified before going to production.** The crypto
providers (CoinGecko, Binance) are fully functional out of the box.

## License

Proprietary — internal project.
