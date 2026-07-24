"""Model contract tests for common notification persistence."""

from sqlalchemy import CheckConstraint

from app.models.notification_model import Notification


def test_notification_model_contains_only_common_typed_columns():
    assert set(Notification.__table__.columns.keys()) == {
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


def test_notification_model_has_closed_type_constraint_and_expected_indexes():
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in Notification.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {index.name: index for index in Notification.__table__.indexes}

    assert constraints["ck_notifications_type"] == ("type IN ('follow.started', 'follow.requested', 'follow.accepted')")
    assert set(indexes) == {
        "ix_notifications_recipient_chronology",
        "ix_notifications_recipient_unread_chronology",
        "uq_notifications_active_recipient_deduplication_key",
    }
    assert indexes["uq_notifications_active_recipient_deduplication_key"].unique is True
    assert (
        indexes["uq_notifications_active_recipient_deduplication_key"].dialect_options["postgresql"]["where"]
        is not None
    )
