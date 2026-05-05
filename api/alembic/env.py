"""Alembic environment.

We don't use the SQLAlchemy ORM in this project -- the runtime app
talks to Postgres via raw asyncpg. Alembic is here for migration
management only, and all migrations are written as raw SQL via
``op.execute(...)``.

The DATABASE_URL comes from ``app.settings`` (which reads .env) so
there's exactly one source of truth. We swap the dialect to
``postgresql+psycopg`` so SQLAlchemy uses psycopg v3 instead of the
legacy psycopg2.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.settings import settings


config = context.config

config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1),
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No ORM models -- migrations are raw SQL only.
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
