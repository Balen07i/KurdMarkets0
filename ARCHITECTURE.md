# Architecture

## Design goals (from the product spec)

Reliable, fast, modular, easy to maintain/extend, low operating cost,
production-ready. Every decision below traces back to one of these.

## Data flow

```
Scrapers (providers/)
    ↓ ProviderReading (in-memory dataclass, not persisted)
worker/jobs/scrape.py
    ↓ RawReading rows (raw_readings table — permanent, append-only)
worker/jobs/reconcile.py → reconciliation/engine.py
    ↓ ReconciliationResult (in-memory)
reconciliation/publisher.py
    ↓ PublishedRate row (published_rates table)
core/redis_client.py (cache)
    ↓
bot/ (reads via history/rates.py) → Telegram users
history/ai_summary.py (reads via history/rates.py) → AISummary → bot/handlers/summary.py
```

**Why two separate tables (`raw_readings` and `published_rates`) instead
of one with a status column?** Auditability and safety. `raw_readings` is
never mutated except a status flip and is kept forever — given any
published price, an admin can always answer "which sources said what, and
which did reconciliation trust?". `published_rates` is the only table the
bot and AI are allowed to query, which makes "the AI only reads published
rates" and "the bot never scrapes data directly" enforceable by which
table a query touches, not just by code review discipline.

## The plugin architecture

Every asset category (`AssetCategory` in `core/enums.py`) and every
concrete asset (`AssetCode`) is data, not code. Adding a new tracked
instrument means:

1. A new `AssetCode` enum value.
2. A new `Asset` row (Alembic data migration).
3. A new `Provider` subclass (`providers/<category>/your_source.py`).
4. A new `Source` row pointing `provider_path` at that class.

The scheduler (`worker/scheduler.py` → `worker/jobs/scrape.py`) never
hardcodes which sources exist — it queries the `sources` table and
resolves `provider_path` dynamically via `providers/registry.py`
(`importlib.import_module` + `getattr`). This is what makes "every asset
category should behave like a plugin" true at the architecture level, not
just conceptually.

## Verification strategy

There is no official ground truth for local market prices, so
"verification" means statistical agreement between independent sources,
implemented in `reconciliation/engine.py`:

1. **Minimum source count.** Fewer than `RECONCILIATION_MIN_SOURCES`
   independent sources reporting → flagged for review, no price computed.
2. **Weighted median.** The candidate value is the median of all
   readings, weighted by each source's `trust_weight` (tunable per source
   by admins over time as a source proves reliable/unreliable).
3. **Tolerance-band outlier rejection.** Any reading more than
   `RECONCILIATION_TOLERANCE_PCT` from the candidate is excluded; the
   median is then recomputed from only the in-tolerance readings.
4. **Re-check source count post-rejection.** If outlier rejection drops
   the count below the minimum, the whole batch is flagged for review —
   a single confidently-wrong source can't force a two-source minimum
   down to a one-source "average".
5. **Confidence scoring.** A 0–1 score blending (a) how tightly the
   in-tolerance readings agree, relative to the tolerance band, and (b)
   what fraction of all reporting sources were actually used. Below
   `RECONCILIATION_MIN_CONFIDENCE`, even a computable price is flagged for
   review rather than trusted.

Every one of these thresholds is an environment variable — see
`.env.example` — precisely because the "right" tolerance for, say, a
volatile local cash market differs from a liquid crypto pair, and this
should be tunable without a code change.

**Why is this pure and DB-agnostic?** `reconcile()` takes plain
dataclasses (`CandidateReading`) and returns a plain dataclass
(`ReconciliationResult`) — no ORM objects, no session. This is what makes
`tests/test_reconciliation_engine.py` able to exhaustively test every
branch (agreement, insufficient sources, disagreement, outlier rejection,
low confidence) with zero database or network dependency. All I/O
(persisting the result, updating readings' status, refreshing the Redis
cache) lives in `reconciliation/publisher.py`, which is deliberately the
*only* code path allowed to write a `PublishedRate`.

## Admin review

A `PublishedRate` row is written even when reconciliation can't
auto-verify — with `status = PENDING_REVIEW` and a human-readable
`review_reason`. It is NOT shown to regular users or read by the AI
summary (both `history/rates.py` and `history/ai_summary.py` filter to
`status == PUBLISHED` only). `/admin` in the bot lists pending rows with
Approve/Reject buttons (`bot/handlers/admin.py`); approving flips the
status to `PUBLISHED` (making it immediately visible, identical to an
auto-published rate from that point on) and records
`reviewed_by_admin_id`/`reviewed_at` for audit.

## The AI summary

`history/ai_summary.py` generates one Kurdish-language summary per
calendar day, strictly from `history/rates.py::get_all_current_rates()`
(verified data only), caches it in both Postgres (`ai_summaries` table,
durable) and Redis (`summary:daily:{date}`, fast reads), and never
regenerates for a given day once it exists (idempotent — checked by the
`summary_date` unique constraint plus a read-before-write check).

Prompts are versioned (`history/prompts/v1.py`, future `v2.py`, ...) and
the version used for a given summary is stored on
`AISummary.prompt_version`, so prompt quality/behavior can be compared
across revisions later. The prompt itself is written with an explicit,
repeated instruction never to invent, estimate, or reference any number
not present in the verified data block it's given — this is a prompting
mitigation, not a technical guarantee, which is why the generator only
ever hands the model data that has already passed reconciliation.

## Monitoring

Four failure modes, per the spec, each with a distinct alert path (all
delivered via `monitoring/notifier.py`, deduped per-message for 30
minutes so a persistent failure doesn't spam admins every scrape cycle):

| Failure mode | Detected in | Alert trigger |
|---|---|---|
| A scraper fails | `worker/jobs/scrape.py` | Immediately, on `ScraperError` |
| Data becomes stale | `worker/jobs/health.py` (every 15 min) | `PublishedRate.effective_at` older than `STALE_THRESHOLD_MINUTES` |
| A source changes (repeated parse failures) | `monitoring/health.py` | Auto-disabled after `DISABLE_FAILURE_THRESHOLD` (10) consecutive failures; degraded-alerted after 3 |
| Reconciliation fails | `worker/jobs/reconcile.py` | Any `PENDING_REVIEW` result |

## Database design notes

- **UUID primary keys** everywhere (not auto-increment ints) — safe to
  reference in logs/URLs without leaking row counts, and can be generated
  before insert.
- **`Numeric`, never `Float`**, for any monetary/rate value — floating
  point rounding error is unacceptable for prices.
- **`published_rates` doubles as the history table.** There's no separate
  `rate_history` table — `PublishedRate` is already append-only (a new
  row per reconciliation cycle, never updated in place except the
  `status`/review fields), so `/history` queries are just a time-bounded
  `SELECT` against it.
- **Gold/silver per-gram is derived, not scraped.** Providers report
  exactly what the source quotes (per-mithqal); `reconciliation/publisher.py`
  computes `price_per_gram = price / settings.mithqal_grams` once, after
  verification, from the single reconciled value — not independently per
  source, which would let sources' differing per-gram-rounding
  conventions become a spurious reconciliation disagreement.

## Testing strategy

The included suite (`tests/`) covers pure business logic with no
database or network: the reconciliation engine, number/digit parsing,
bot-side formatting, provider resolution, and settings parsing. This is
deliberate — it runs in milliseconds in any environment (including CI
with no service dependencies) and exhaustively covers the
highest-consequence logic (verification correctness) via unit tests.

Adding a DB-backed integration suite (recommended before scaling past the
current provider set) means pointing `DATABASE_URL`/`DATABASE_URL_SYNC` at
a disposable test database (e.g. a Dockerized Postgres in CI), running
`alembic upgrade head` against it, and writing tests against
`core.db.session_scope()` the same way application code does — no
separate test-only data-access layer needed, since `history/rates.py`
and `reconciliation/publisher.py` already are that layer.
