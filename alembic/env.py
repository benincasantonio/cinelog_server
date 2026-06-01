"""Alembic environment for async PostgreSQL migrations."""

import asyncio
import os
from logging.config import fileConfig
from typing import Any

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all ORM modules so their tables register with ``Base.metadata`` before
# ``--autogenerate`` snapshots it. Imports are side-effect only.
from alembic import context, util
from app.models import movie_model, user_model  # noqa: F401
from app.models.base_model import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
DATABASE_URL_ENV = "DATABASE_URL"


def _get_alembic_database_url() -> str:
    database_url = os.getenv(DATABASE_URL_ENV)
    if database_url:
        return database_url

    raise util.CommandError(
        f"{DATABASE_URL_ENV} is required to run Alembic migrations. "
        "Set it to a postgresql+asyncpg:// connection string before running Alembic."
    )


def run_migrations_offline() -> None:
    """Run migrations without opening a database connection."""
    context.configure(
        url=_get_alembic_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations against an existing connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations."""
    section = config.get_section(config.config_ini_section, {})
    configuration: dict[str, Any] = dict(section)
    configuration["sqlalchemy.url"] = _get_alembic_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
