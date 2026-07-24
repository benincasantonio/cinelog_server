"""PostgreSQL integration tests for the notification-table migration."""

from uuid import UUID

import pytest
from psycopg.errors import CheckViolation, UniqueViolation

from app.types import NotificationType
from tests.alembic_test_harness import AlembicTestHarness

PREVIOUS_REVISION = "005_rename_profile_visibility"


def _insert_user(harness: AlembicTestHarness, *, suffix: str) -> UUID:
    with harness.connect() as connection:
        row = connection.execute(
            """
            INSERT INTO users (email, handle, first_name, last_name)
            VALUES (%s, %s, 'Notification', 'User')
            RETURNING id
            """,
            (f"notification-{suffix}@example.com", f"notification-{suffix}"),
        ).fetchone()
    assert row is not None
    return row[0]


def _insert_notification(
    harness: AlembicTestHarness,
    *,
    recipient_id: UUID,
    notification_type: str = "follow.started",
    actor_id: UUID | None = None,
    deduplication_key: str | None = None,
) -> UUID:
    with harness.connect() as connection:
        row = connection.execute(
            """
            INSERT INTO notifications (recipient_id, actor_id, type, title, body, deduplication_key)
            VALUES (%s, %s, %s, 'Title', 'Body', %s)
            RETURNING id
            """,
            (recipient_id, actor_id, notification_type, deduplication_key),
        ).fetchone()
    assert row is not None
    return row[0]


def test_notification_migration_enforces_closed_common_schema(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade(PREVIOUS_REVISION)
    alembic_test_harness.upgrade()

    with alembic_test_harness.connect() as connection:
        columns = connection.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'notifications'
            ORDER BY ordinal_position
            """
        ).fetchall()
        indexes = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'notifications'"
            ).fetchall()
        }

    assert {column[0] for column in columns} == {
        "id",
        "recipient_id",
        "actor_id",
        "type",
        "title",
        "body",
        "deduplication_key",
        "read_at",
        "deleted",
        "deleted_at",
        "created_at",
        "updated_at",
    }
    assert {column[0]: column[1] for column in columns}["type"] == "text"
    assert set(indexes) >= {
        "ix_notifications_recipient_chronology",
        "ix_notifications_recipient_unread_chronology",
        "uq_notifications_active_recipient_deduplication_key",
    }
    assert (
        "WHERE ((deleted IS FALSE) AND (deduplication_key IS NOT NULL))"
        in indexes["uq_notifications_active_recipient_deduplication_key"]
    )

    recipient_id = _insert_user(alembic_test_harness, suffix="closed-type")
    # Driving this from the enum keeps the migrated CHECK constraint from drifting
    # behind a newly registered NotificationType member.
    for notification_type in NotificationType:
        _insert_notification(
            alembic_test_harness,
            recipient_id=recipient_id,
            notification_type=notification_type.value,
        )

    with pytest.raises(CheckViolation):
        _insert_notification(
            alembic_test_harness,
            recipient_id=recipient_id,
            notification_type="unknown.event",
        )


def test_notification_migration_enforces_recipient_deduplication_and_fk_deletes(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade()
    recipient_id = _insert_user(alembic_test_harness, suffix="recipient")
    other_recipient_id = _insert_user(alembic_test_harness, suffix="other-recipient")
    actor_id = _insert_user(alembic_test_harness, suffix="actor")

    first_id = _insert_notification(
        alembic_test_harness,
        recipient_id=recipient_id,
        actor_id=actor_id,
        deduplication_key="shared-event",
    )
    with pytest.raises(UniqueViolation):
        _insert_notification(
            alembic_test_harness,
            recipient_id=recipient_id,
            deduplication_key="shared-event",
        )

    _insert_notification(
        alembic_test_harness,
        recipient_id=other_recipient_id,
        deduplication_key="shared-event",
    )

    with alembic_test_harness.connect() as connection:
        connection.execute("UPDATE notifications SET deleted = TRUE WHERE id = %s", (first_id,))

    replacement_id = _insert_notification(
        alembic_test_harness,
        recipient_id=recipient_id,
        actor_id=actor_id,
        deduplication_key="shared-event",
    )
    with alembic_test_harness.connect() as connection:
        connection.execute("DELETE FROM users WHERE id = %s", (actor_id,))
        actor_row = connection.execute(
            "SELECT actor_id FROM notifications WHERE id = %s",
            (replacement_id,),
        ).fetchone()
        assert actor_row == (None,)

        connection.execute("DELETE FROM users WHERE id = %s", (recipient_id,))
        assert connection.execute(
            "SELECT count(*) FROM notifications WHERE recipient_id = %s",
            (recipient_id,),
        ).fetchone() == (0,)


def test_notification_migration_downgrades_cleanly(alembic_test_harness: AlembicTestHarness):
    alembic_test_harness.upgrade()

    alembic_test_harness.downgrade(PREVIOUS_REVISION)

    with alembic_test_harness.connect() as connection:
        assert connection.execute("SELECT to_regclass('notifications')").fetchone() == (None,)
