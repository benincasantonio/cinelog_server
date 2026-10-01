import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db import postgres


@pytest_asyncio.fixture(autouse=True)
async def reset_postgres_engine():
    await postgres.close_postgres_engine()
    yield
    await postgres.close_postgres_engine()


def test_postgres_engine_init_raises_when_database_url_is_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(postgres.PostgresConfigurationError, match="DATABASE_URL"):
        postgres.init_postgres_engine()


def test_postgres_engine_init_creates_reusable_engine(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/cinelog_test")

    engine = postgres.init_postgres_engine()

    assert isinstance(engine, AsyncEngine)
    assert postgres.init_postgres_engine() is engine
    assert postgres.async_session_factory is not None


async def test_get_async_session_yields_async_session(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/cinelog_test")

    async with postgres.get_async_session() as session:
        assert isinstance(session, AsyncSession)
