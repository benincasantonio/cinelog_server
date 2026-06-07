"""Async PostgreSQL engine and session management."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal, cast, overload

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL_ENV = "DATABASE_URL"
DB_BACKEND_ENV = "DB_BACKEND"
ASYNC_POSTGRES_SCHEME = "postgresql+asyncpg://"
POSTGRES_SCHEME = "postgres://"
POSTGRESQL_SCHEME = "postgresql://"


class PostgresConfigurationError(RuntimeError):
    """Raised when PostgreSQL is required but not configured."""


_engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def is_postgres_required() -> bool:
    """Return whether the configured database backend requires PostgreSQL."""
    return os.getenv(DB_BACKEND_ENV, "").strip().lower() == "postgres"


@overload
def get_database_url(*, required: Literal[True] = True) -> str: ...


@overload
def get_database_url(*, required: Literal[False]) -> str | None: ...


@overload
def get_database_url(*, required: bool) -> str | None: ...


def get_database_url(*, required: bool = True) -> str | None:
    """Return the configured PostgreSQL database URL."""
    database_url = os.getenv(DATABASE_URL_ENV)
    if database_url:
        return normalize_database_url(database_url)

    if required:
        raise PostgresConfigurationError(
            f"{DATABASE_URL_ENV} is required to initialize PostgreSQL. "
            "Set it to a postgresql+asyncpg:// connection string."
        )

    return None


def normalize_database_url(database_url: str) -> str:
    """Normalize common hosted Postgres URLs for SQLAlchemy asyncpg."""
    if database_url.startswith(ASYNC_POSTGRES_SCHEME):
        return database_url

    if database_url.startswith(POSTGRESQL_SCHEME):
        return f"{ASYNC_POSTGRES_SCHEME}{database_url.removeprefix(POSTGRESQL_SCHEME)}"

    if database_url.startswith(POSTGRES_SCHEME):
        return f"{ASYNC_POSTGRES_SCHEME}{database_url.removeprefix(POSTGRES_SCHEME)}"

    return database_url


@overload
def init_postgres_engine(*, required: Literal[True]) -> AsyncEngine: ...


@overload
def init_postgres_engine(*, required: Literal[False]) -> AsyncEngine | None: ...


@overload
def init_postgres_engine(*, required: None = None) -> AsyncEngine | None: ...


def init_postgres_engine(*, required: bool | None = None) -> AsyncEngine | None:
    """Initialize the process-wide async PostgreSQL engine if configured."""
    global _engine, async_session_factory

    if _engine is not None:
        return _engine

    should_require_postgres = is_postgres_required() if required is None else required
    database_url = get_database_url(required=should_require_postgres)
    if database_url is None:
        return None

    _engine = create_async_engine(database_url, pool_pre_ping=True)
    async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_postgres_engine() -> AsyncEngine:
    """Return the configured PostgreSQL engine, initializing it if needed."""
    return init_postgres_engine(required=True)


@asynccontextmanager
async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy session for PostgreSQL repositories."""
    global async_session_factory

    if async_session_factory is None:
        init_postgres_engine(required=True)

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
