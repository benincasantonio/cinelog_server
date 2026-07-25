"""Model contract tests for outbound-message (transactional outbox) persistence."""

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.outbound_message_model import OutboundMessage


def test_outbound_message_model_contains_expected_columns():
    assert set(OutboundMessage.__table__.columns.keys()) == {
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
        "expires_at",
        "lock_token",
        "deleted",
        "deleted_at",
        "created_at",
        "updated_at",
    }


def test_outbound_message_model_has_expected_check_constraints():
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in OutboundMessage.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert constraints["ck_outbound_messages_kind"] == (
        "kind IN ('notification', 'registration_verification', 'registration_existing_account', 'password_reset')"
    )
    assert constraints["ck_outbound_messages_channel"] == "channel IN ('email')"
    assert (
        constraints["ck_outbound_messages_status"]
        == "status IN ('pending', 'processing', 'delivered', 'failed', 'cancelled')"
    )
    assert constraints["ck_outbound_messages_notification_reference"] == (
        "(kind = 'notification') = (notification_id IS NOT NULL)"
    )
    assert constraints["ck_outbound_messages_attempt_count"] == "attempt_count >= 0"
    assert constraints["ck_outbound_messages_last_error_length"] == (
        "last_error IS NULL OR char_length(last_error) <= 500"
    )


def test_outbound_message_model_has_total_unique_constraint_on_notification_and_channel():
    unique_constraints = {
        constraint.name: constraint
        for constraint in OutboundMessage.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    constraint = unique_constraints["uq_outbound_messages_notification_channel"]
    assert {column.name for column in constraint.columns} == {"notification_id", "channel"}


def test_outbound_message_model_has_expected_partial_indexes():
    indexes = {index.name: index for index in OutboundMessage.__table__.indexes}

    assert set(indexes) == {
        "ix_outbound_messages_claimable",
        "ix_outbound_messages_stale_locks",
        # Both maintenance sweeps need their own index: neither the claimable nor the
        # stale-lock index covers settled rows or expiry, so they would scan the table.
        "ix_outbound_messages_expiring",
        "ix_outbound_messages_retention",
    }

    claimable = indexes["ix_outbound_messages_claimable"]
    assert [column.name for column in claimable.columns] == ["channel", "available_at", "id"]
    assert claimable.dialect_options["postgresql"]["where"] is not None

    stale_locks = indexes["ix_outbound_messages_stale_locks"]
    assert [column.name for column in stale_locks.columns] == ["locked_at"]
    assert stale_locks.dialect_options["postgresql"]["where"] is not None


def test_outbound_message_model_has_no_orm_relationships():
    assert OutboundMessage.__mapper__.relationships.keys() == []
