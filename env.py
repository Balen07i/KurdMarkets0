"""Alembic migration environment.

Deliberately uses the SYNCHRONOUS database URL (`DATABASE_URL_SYNC`, via
psycopg2) even though the application runs on the async engine — Alembic's
autogenerate and offline-mode support for async engines is still rougher
than sync, and migrations are a one-shot CLI operation where async
concurrency buys nothing.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import settings + all models so `target_metadata` is fully populated and
# the DB URL comes from one validated place instead of being duplicated in
# alembic.ini.
from core.config import settings
from core.models import Base  # noqa: F401 — triggers model imports for metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override whatever (blank) sqlalchemy.url is in alembic.ini with the real,
# validated one from application settings.
config.set_main_option("sqlalchemy.url", settings.database_url_sync)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a DB
    connection — used for `alembic upgrade --sql`)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
