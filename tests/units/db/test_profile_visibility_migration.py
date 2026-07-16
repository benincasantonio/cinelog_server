"""Integration coverage for the profile-visibility Alembic migration."""

import pytest
from psycopg.errors import CheckViolation

from tests.alembic_test_harness import AlembicTestHarness

PREVIOUS_REVISION = "004_create_logs_table"


def _insert_user(harness: AlembicTestHarness, *, email: str, handle: str, visibility: str) -> None:
    with harness.connect() as connection:
        connection.execute(
            """
            INSERT INTO users (email, handle, first_name, last_name, profile_visibility)
            VALUES (%s, %s, 'Migration', 'Test', %s)
            """,
            (email, handle, visibility),
        )


def _profile_visibilities(harness: AlembicTestHarness) -> list[str]:
    with harness.connect() as connection:
        rows = connection.execute("SELECT profile_visibility FROM users ORDER BY email").fetchall()
    return [row[0] for row in rows]


def _constraint_definition(harness: AlembicTestHarness) -> str:
    with harness.connect() as connection:
        row = connection.execute(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'users'::regclass
              AND conname = 'ck_users_profile_visibility'
            """
        ).fetchone()
    assert row is not None
    return row[0]


def test_profile_visibility_migration_converts_data_and_replaces_constraint(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade(PREVIOUS_REVISION)
    _insert_user(
        alembic_test_harness,
        email="legacy@example.com",
        handle="legacyuser",
        visibility="friends_only",
    )

    alembic_test_harness.upgrade()

    assert _profile_visibilities(alembic_test_harness) == ["followers_only"]
    upgraded_constraint = _constraint_definition(alembic_test_harness)
    assert "followers_only" in upgraded_constraint
    assert "friends_only" not in upgraded_constraint

    _insert_user(
        alembic_test_harness,
        email="follower@example.com",
        handle="followeruser",
        visibility="followers_only",
    )
    with pytest.raises(CheckViolation):
        _insert_user(
            alembic_test_harness,
            email="rejected@example.com",
            handle="rejecteduser",
            visibility="friends_only",
        )

    alembic_test_harness.downgrade(PREVIOUS_REVISION)

    assert _profile_visibilities(alembic_test_harness) == ["friends_only", "friends_only"]
    downgraded_constraint = _constraint_definition(alembic_test_harness)
    assert "friends_only" in downgraded_constraint
    assert "followers_only" not in downgraded_constraint

    with pytest.raises(CheckViolation):
        _insert_user(
            alembic_test_harness,
            email="downgrade-rejected@example.com",
            handle="downgraderejected",
            visibility="followers_only",
        )
