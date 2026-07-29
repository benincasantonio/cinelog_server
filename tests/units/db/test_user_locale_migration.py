"""PostgreSQL integration tests for the user-locale migration."""

import pytest
from psycopg.errors import CheckViolation

from tests.alembic_test_harness import AlembicTestHarness

PREVIOUS_REVISION = "007_create_user_follows_table"


def _insert_user(harness: AlembicTestHarness, *, suffix: str) -> None:
    with harness.connect() as connection:
        connection.execute(
            """
            INSERT INTO users (email, handle, first_name, last_name)
            VALUES (%s, %s, 'Locale', 'User')
            """,
            (f"locale-{suffix}@example.com", f"locale-{suffix}"),
        )


def test_user_locale_migration_backfills_existing_users_and_sets_default(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade(PREVIOUS_REVISION)
    _insert_user(alembic_test_harness, suffix="existing")

    alembic_test_harness.upgrade()
    _insert_user(alembic_test_harness, suffix="new")

    with alembic_test_harness.connect() as connection:
        rows = connection.execute("SELECT handle, locale FROM users ORDER BY handle").fetchall()
        column = connection.execute(
            """
            SELECT is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'locale'
            """
        ).fetchone()

    assert rows == [
        ("locale-existing", "en-US"),
        ("locale-new", "en-US"),
    ]
    assert column is not None
    assert column[0] == "NO"
    assert "'en-US'::text" in column[1]


def test_user_locale_migration_enforces_supported_values(alembic_test_harness: AlembicTestHarness):
    alembic_test_harness.upgrade()

    with alembic_test_harness.connect() as connection:
        connection.execute(
            """
            INSERT INTO users (email, handle, first_name, last_name, locale)
            VALUES ('valid-locale@example.com', 'valid-locale', 'Valid', 'Locale', 'it-IT')
            """
        )

    with pytest.raises(CheckViolation):
        with alembic_test_harness.connect() as connection:
            connection.execute(
                """
                INSERT INTO users (email, handle, first_name, last_name, locale)
                VALUES ('invalid-locale@example.com', 'invalid-locale', 'Invalid', 'Locale', 'de-DE')
                """
            )


def test_user_locale_migration_downgrades_cleanly(alembic_test_harness: AlembicTestHarness):
    alembic_test_harness.upgrade()

    alembic_test_harness.downgrade(PREVIOUS_REVISION)

    with alembic_test_harness.connect() as connection:
        column = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'locale'
            """
        ).fetchone()

    assert column is None
