"""Shared fixtures for PostgreSQL and Alembic database tests."""

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import URL

from tests.alembic_test_harness import AlembicTestHarness, PostgresConnectionParams

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def alembic_test_harness(postgresql_proc, monkeypatch) -> Iterator[AlembicTestHarness]:
    """Provide Alembic and SQL access to a fresh PostgreSQL database."""
    database_name = f"cinelog_migration_test_{uuid4().hex[:8]}"
    connection_params: PostgresConnectionParams = {
        "host": postgresql_proc.host,
        "port": postgresql_proc.port,
        "user": postgresql_proc.user,
        "password": postgresql_proc.password,
        "dbname": database_name,
    }

    with DatabaseJanitor(
        user=postgresql_proc.user,
        host=postgresql_proc.host,
        port=postgresql_proc.port,
        dbname=database_name,
        version=postgresql_proc.version,
        password=postgresql_proc.password,
    ):
        database_url = URL.create(
            "postgresql+asyncpg",
            username=postgresql_proc.user,
            password=postgresql_proc.password,
            host=postgresql_proc.host,
            port=postgresql_proc.port,
            database=database_name,
        )
        monkeypatch.setenv("DATABASE_URL", database_url.render_as_string(hide_password=False))

        config = Config(PROJECT_ROOT / "alembic.ini")
        config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
        yield AlembicTestHarness(config=config, connection_params=connection_params)
