"""PostgreSQL integration tests for the outbound_messages-table migration."""

from uuid import UUID

import pytest
from psycopg.errors import CheckViolation, UniqueViolation

from app.types import OutboundMessageChannel, OutboundMessageKind, OutboundMessageStatus
from tests.alembic_test_harness import AlembicTestHarness

PREVIOUS_REVISION = "006_create_notifications_table"


def _insert_user(harness: AlembicTestHarness, *, suffix: str) -> UUID:
    with harness.connect() as connection:
        row = connection.execute(
            """
            INSERT INTO users (email, handle, first_name, last_name)
            VALUES (%s, %s, 'Outbound', 'User')
            RETURNING id
            """,
            (f"outbound-{suffix}@example.com", f"outbound-{suffix}"),
        ).fetchone()
    assert row is not None
    return row[0]


def _insert_notification(harness: AlembicTestHarness, *, recipient_id: UUID) -> UUID:
    with harness.connect() as connection:
        row = connection.execute(
            """
            INSERT INTO notifications (recipient_id, type, title, body)
            VALUES (%s, 'follow.started', 'Title', 'Body')
            RETURNING id
            """,
            (recipient_id,),
        ).fetchone()
    assert row is not None
    return row[0]


def _insert_outbound_message(
    harness: AlembicTestHarness,
    *,
    kind: str = "registration_verification",
    notification_id: UUID | None = None,
    channel: str = "email",
    destination: str = "user@example.com",
    subject: str = "Subject",
    status: str = "pending",
    last_error: str | None = None,
) -> UUID:
    with harness.connect() as connection:
        row = connection.execute(
            """
            INSERT INTO outbound_messages (kind, notification_id, channel, destination, subject, status, last_error)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (kind, notification_id, channel, destination, subject, status, last_error),
        ).fetchone()
    assert row is not None
    return row[0]


def test_outbound_message_migration_creates_expected_columns_and_indexes(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade(PREVIOUS_REVISION)
    alembic_test_harness.upgrade()

    with alembic_test_harness.connect() as connection:
        columns = connection.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'outbound_messages'
            ORDER BY ordinal_position
            """
        ).fetchall()
        indexes = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'outbound_messages'"
            ).fetchall()
        }

    assert {column[0] for column in columns} == {
        "id",
        "kind",
        "notification_id",
        "channel",
        "destination",
        "subject",
        "text_body",
        "html_body",
        "status",
        "attempt_count",
        "available_at",
        "locked_at",
        "delivered_at",
        "last_error",
        "deleted",
        "deleted_at",
        "created_at",
        "updated_at",
    }
    nullability = {column[0]: column[2] for column in columns}
    assert nullability["kind"] == "NO"
    assert nullability["notification_id"] == "YES"
    assert nullability["status"] == "NO"
    assert nullability["attempt_count"] == "NO"

    assert set(indexes) >= {"ix_outbound_messages_claimable", "ix_outbound_messages_stale_locks"}
    claimable_def = indexes["ix_outbound_messages_claimable"]
    assert "deleted IS FALSE" in claimable_def
    assert "status = 'pending'" in claimable_def

    stale_locks_def = indexes["ix_outbound_messages_stale_locks"]
    assert "deleted IS FALSE" in stale_locks_def
    assert "status = 'processing'" in stale_locks_def


def test_outbound_message_migration_enforces_closed_enum_membership(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade()
    recipient_id = _insert_user(alembic_test_harness, suffix="closed-enum")
    notification_id = _insert_notification(alembic_test_harness, recipient_id=recipient_id)

    # Driving this from the enums keeps the migrated CHECK constraints from drifting
    # behind a newly registered OutboundMessageKind/Channel/Status member.
    for kind in OutboundMessageKind:
        _insert_outbound_message(
            alembic_test_harness,
            kind=kind.value,
            notification_id=notification_id if kind is OutboundMessageKind.NOTIFICATION else None,
            channel=OutboundMessageChannel.EMAIL.value,
        )

    for channel in OutboundMessageChannel:
        _insert_outbound_message(alembic_test_harness, channel=channel.value)

    for status in OutboundMessageStatus:
        _insert_outbound_message(alembic_test_harness, status=status.value)

    with pytest.raises(CheckViolation):
        _insert_outbound_message(alembic_test_harness, kind="unknown_kind")

    with pytest.raises(CheckViolation):
        _insert_outbound_message(alembic_test_harness, channel="sms")

    with pytest.raises(CheckViolation):
        _insert_outbound_message(alembic_test_harness, status="unknown_status")


def test_outbound_message_migration_enforces_kind_notification_reference_both_ways(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade()
    recipient_id = _insert_user(alembic_test_harness, suffix="reference")
    notification_id = _insert_notification(alembic_test_harness, recipient_id=recipient_id)

    with pytest.raises(CheckViolation):
        _insert_outbound_message(alembic_test_harness, kind="notification", notification_id=None)

    with pytest.raises(CheckViolation):
        _insert_outbound_message(
            alembic_test_harness,
            kind="registration_verification",
            notification_id=notification_id,
        )


def test_outbound_message_migration_unique_constraint_allows_distinct_null_notification_ids(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade()
    recipient_id = _insert_user(alembic_test_harness, suffix="unique")
    notification_id = _insert_notification(alembic_test_harness, recipient_id=recipient_id)

    _insert_outbound_message(alembic_test_harness, kind="notification", notification_id=notification_id)
    with pytest.raises(UniqueViolation):
        _insert_outbound_message(alembic_test_harness, kind="notification", notification_id=notification_id)

    # PostgreSQL treats NULL as distinct from NULL, so two auth-kind (NULL notification_id)
    # rows on the same channel coexist without violating the constraint.
    _insert_outbound_message(alembic_test_harness, kind="registration_verification", notification_id=None)
    _insert_outbound_message(alembic_test_harness, kind="password_reset", notification_id=None)


def test_outbound_message_migration_rejects_last_error_over_500_characters(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade()

    _insert_outbound_message(alembic_test_harness, last_error="x" * 500)

    with pytest.raises(CheckViolation):
        _insert_outbound_message(alembic_test_harness, last_error="x" * 501)


def test_outbound_message_migration_cascades_delete_from_notifications(
    alembic_test_harness: AlembicTestHarness,
):
    alembic_test_harness.upgrade()
    recipient_id = _insert_user(alembic_test_harness, suffix="cascade")
    notification_id = _insert_notification(alembic_test_harness, recipient_id=recipient_id)
    _insert_outbound_message(alembic_test_harness, kind="notification", notification_id=notification_id)

    with alembic_test_harness.connect() as connection:
        connection.execute("DELETE FROM notifications WHERE id = %s", (notification_id,))
        remaining = connection.execute(
            "SELECT count(*) FROM outbound_messages WHERE notification_id = %s",
            (notification_id,),
        ).fetchone()
        assert remaining == (0,)


def test_outbound_message_migration_downgrades_cleanly(alembic_test_harness: AlembicTestHarness):
    alembic_test_harness.upgrade()

    alembic_test_harness.downgrade(PREVIOUS_REVISION)

    with alembic_test_harness.connect() as connection:
        assert connection.execute("SELECT to_regclass('outbound_messages')").fetchone() == (None,)
