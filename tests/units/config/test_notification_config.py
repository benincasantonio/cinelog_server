"""Tests for notification-domain configuration."""

from uuid import uuid4

from app.config.notification_config import notification_list_cursor_scope


def test_notification_list_cursor_scope_is_unique_per_recipient():
    recipient_id = uuid4()
    other_recipient_id = uuid4()

    assert notification_list_cursor_scope(recipient_id) == f"notifications.list:{recipient_id}"
    assert notification_list_cursor_scope(recipient_id) == notification_list_cursor_scope(recipient_id)
    assert notification_list_cursor_scope(recipient_id) != notification_list_cursor_scope(other_recipient_id)
