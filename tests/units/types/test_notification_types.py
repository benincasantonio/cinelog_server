"""Contract tests for closed notification types and actions."""

from pathlib import Path

import pytest

from app.types import NotificationAction, NotificationType


def test_notification_type_contains_only_registered_values():
    assert [notification_type.value for notification_type in NotificationType] == [
        "follow.started",
        "follow.requested",
        "follow.accepted",
    ]


def test_notification_action_contains_only_registered_values():
    assert [action.value for action in NotificationAction] == [
        "follow_request.accept",
        "follow_request.reject",
    ]


def test_notification_enums_reject_unknown_values():
    with pytest.raises(ValueError):
        NotificationType("unknown.event")

    with pytest.raises(ValueError):
        NotificationAction("unknown.action")


def test_raw_notification_action_values_are_declared_once_in_application_code():
    app_root = Path(__file__).resolve().parents[3] / "app"
    allowed_path = app_root / "types" / "notification_types.py"

    for path in app_root.rglob("*.py"):
        if path == allowed_path:
            continue
        source = path.read_text()
        assert "follow_request.accept" not in source
        assert "follow_request.reject" not in source
