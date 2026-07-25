# Deployment (Railway)

This project deploys as **two separate Railway services** from the same
repository, sharing one Postgres and one Redis plugin.

## 1. Create the project and plugins

1. Create a new Railway project from this repo.
2. Add a **PostgreSQL** plugin. Railway injects `DATABASE_URL`
   automatically into every service in the project. Also set
   `DATABASE_URL_SYNC` on both services manually (same connection info,
   `postgresql+psycopg2://...` instead of the async driver — Alembic uses
   the sync URL; see `core/config.py`).
3. Add a **Redis** plugin. Railway injects `REDIS_URL` automatically.

## 2. The `bot` service (default)

Uses the repo root `railway.toml` as-is:

- Build: `pip install -r requirements.txt` (Nixpacks)
- Start: `python -m bot.main`
- Health check: `GET /health` (served by the bot's own tiny aiohttp
  server — see `bot/main.py`), since long-polling alone exposes no port.

Set these Variables on the service (see `.env.example` for the full
list; these are the ones the bot process needs):

- `TELEGRAM_BOT_TOKEN` (required)
- `TELEGRAM_ADMIN_IDS`
- `DATABASE_URL_SYNC` (Alembic; async `DATABASE_URL` is auto-injected)
- `APP_ENV=production`
- `LOG_LEVEL=INFO`

## 3. The `worker` service

Add a **second service** in the same Railway project, pointing at the
same repo/branch, then override its **Start Command** in the service's
Settings tab to:

```
python -m worker.main
```

(Leave the build command as the Nixpacks default — same
`requirements.txt` install as the bot service.) This service has no
`/health` endpoint and does not need a public domain — disable networking
for it in Railway's settings if you want to avoid an unused public URL.

Set these additional Variables on the worker service:

- `TELEGRAM_BOT_TOKEN` (needed to send admin alerts + alert notifications)
- `TELEGRAM_ADMIN_IDS`
- `ANTHROPIC_API_KEY` (required for the daily AI summary job)
- `DATABASE_URL_SYNC`
- All `SCRAPE_INTERVAL_*` / `RECONCILIATION_*` / `STALE_THRESHOLD_MINUTES`
  variables you want to override from their defaults.

## 4. Running migrations

Migrations are NOT run automatically on every deploy boot (running
`alembic upgrade head` from application startup code is avoided
deliberately — with two services deploying from the same repo, both
starting simultaneously could race to run migrations concurrently).
Instead:

- The `Procfile`'s `release: alembic upgrade head` line runs once per
  deploy on platforms that support Procfile release phases.
- On Railway specifically (which does not auto-run Procfile release
  commands as of this writing), run migrations manually after each deploy
  that changes the schema:

  ```bash
  railway run --service bot alembic upgrade head
  ```

  (Either service works — both have identical code and `DATABASE_URL_SYNC`.)

## 5. First deploy checklist

1. Deploy both services with the variables above set.
2. Run `alembic upgrade head` (creates schema + seeds `assets`/`sources`).
3. Verify `GET https://<bot-service-domain>/health` returns
   `{"status": "ok", ...}`.
4. Message your bot `/start` on Telegram — you should see the main menu.
5. **Before relying on any non-crypto data**: go through every provider
   file with a `TODO` (see README → "Configuring real data sources"),
   pick real sources, verify selectors, and update the corresponding
   `Source.provider_path`/URLs. Until then, currency/gold/silver/fuel
   scrapes will fail loudly (admin alerts fire) rather than silently
   publishing placeholder data — this is intentional.
6. Confirm admin alerts arrive: temporarily lower
   `RECONCILIATION_MIN_SOURCES` to trigger a test, or just wait for the
   first scheduled scrape cycle against the still-placeholder URLs.

## Rollback

Railway keeps prior deployments; roll back a service from its Deployments
tab. Database migrations are NOT automatically rolled back on a service
rollback — if a bad deploy included a migration, run
`alembic downgrade -1` manually before rolling back the code, or accept
the (additive-by-convention) schema staying ahead of the rolled-back code
if the migration was purely additive.
