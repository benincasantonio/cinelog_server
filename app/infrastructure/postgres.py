"""Async PostgreSQL engine and session management."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL_ENV = "DATABASE_URL"


class PostgresConfigurationError(RuntimeError):
    """Raised when PostgreSQL is required but not configured."""


_engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    """Return the configured PostgreSQL database URL."""
    database_url = os.getenv(DATABASE_URL_ENV)
    if database_url:
        return database_url

    raise PostgresConfigurationError(
        f"{DATABASE_URL_ENV} is required to initialize PostgreSQL. Set it to a postgresql+asyncpg:// connection string."
    )


def init_postgres_engine() -> AsyncEngine:
    """Initialize the process-wide async PostgreSQL engine."""
    global _engine, async_session_factory

    if _engine is not None:
        return _engine

    _engine = create_async_engine(get_database_url(), pool_pre_ping=True)
    async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_postgres_engine() -> AsyncEngine:
    """Return the configured PostgreSQL engine, initializing it if needed."""
    return init_postgres_engine()


@asynccontextmanager
async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy session for PostgreSQL repositories."""
    global async_session_factory

    if async_session_factory is None:
        init_postgres_engine()

    session_factory = cast("async_sessionmaker[AsyncSession]", async_session_factory)

    async with session_factory() as session:
        yield session


async def close_postgres_engine() -> None:
    """Dispose the PostgreSQL engine and clear process-wide session state."""
    global _engine, async_session_factory

    if _engine is not None:
        await _engine.dispose()

    _engine = None
    async_session_factory = None
