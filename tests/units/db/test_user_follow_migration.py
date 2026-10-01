"""PostgreSQL integration tests for the user-follows migration."""

from uuid import UUID

import pytest
from psycopg.errors import CheckViolation, UniqueViolation

from tests.alembic_test_harness import AlembicTestHarness

PREVIOUS_REVISION = "006_create_notifications_table"


def _insert_user(harness: AlembicTestHarness, *, suffix: str) -> UUID:
    with harness.connect() as connection:
        row = connection.execute(
            """
            INSERT INTO users (email, handle, first_name, last_name)
            VALUES (%s, %s, 'Follow', 'User')
            RETURNING id
            """,
            (f"follow-{suffix}@example.com", f"follow-{suffix}"),
        ).fetchone()
    assert row is not None
    return row[0]


def _insert_follow(harness: AlembicTestHarness, follower_id: UUID, followed_id: UUID) -> None:
    with harness.connect() as connection:
        connection.execute(
            "INSERT INTO user_follows (follower_id, followed_id) VALUES (%s, %s)",
            (follower_id, followed_id),
        )


def test_user_follow_migration_creates_minimal_indexed_edge_table(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade(PREVIOUS_REVISION)
    alembic_test_harness.upgrade()

    with alembic_test_harness.connect() as connection:
        columns = connection.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'user_follows'
            ORDER BY ordinal_position
            """
        ).fetchall()
        indexes = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'user_follows'"
            ).fetchall()
        }

    assert {column[0] for column in columns} == {
        "follower_id",
        "followed_id",
        "created_at",
    }
    assert all(column[2] == "NO" for column in columns)
    assert set(indexes) >= {
        "user_follows_pkey",
        "ix_user_follows_followed_id",
    }


def test_user_follow_migration_enforces_constraints_and_cascades(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade()
    follower_id = _insert_user(alembic_test_harness, suffix="follower")
    followed_id = _insert_user(alembic_test_harness, suffix="followed")

    _insert_follow(alembic_test_harness, follower_id, followed_id)

    with pytest.raises(UniqueViolation):
        _insert_follow(alembic_test_harness, follower_id, followed_id)
    with pytest.raises(CheckViolation):
        _insert_follow(alembic_test_harness, follower_id, follower_id)

    with alembic_test_harness.connect() as connection:
        connection.execute("DELETE FROM users WHERE id = %s", (followed_id,))
        count = connection.execute("SELECT count(*) FROM user_follows").fetchone()
    assert count == (0,)


def test_user_follow_migration_downgrades_cleanly(alembic_test_harness: AlembicTestHarness):
    alembic_test_harness.upgrade()

    alembic_test_harness.downgrade(PREVIOUS_REVISION)

    with alembic_test_harness.connect() as connection:
        assert connection.execute("SELECT to_regclass('user_follows')").fetchone() == (None,)
