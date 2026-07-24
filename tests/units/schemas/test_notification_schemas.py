"""Tests for notification request and response wire contracts."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.notification_schemas import (
    MAX_CURSOR_LENGTH,
    BasicUserSummary,
    MarkAllNotificationsReadResponse,
    NotificationBaseResponse,
    NotificationListRequest,
    NotificationListResponse,
)
from app.types import NotificationAction, NotificationType


def _notification_response() -> NotificationBaseResponse:
    return NotificationBaseResponse(
        id=uuid4(),
        type=NotificationType.FOLLOW_REQUESTED,
        title="New follow request",
        body="A user requested to follow you.",
        actor=BasicUserSummary(handle="viewer", first_name="View", last_name="Er"),
        available_actions=[
            NotificationAction.FOLLOW_REQUEST_ACCEPT,
            NotificationAction.FOLLOW_REQUEST_REJECT,
        ],
        read_at=None,
        created_at=datetime(2026, 7, 18, 8, 30, tzinfo=UTC),
    )


def test_notification_response_uses_camel_case_and_serializes_enum_values():
    payload = _notification_response().model_dump(mode="json", by_alias=True)

    assert payload["type"] == "follow.requested"
    assert payload["availableActions"] == ["follow_request.accept", "follow_request.reject"]
    assert payload["readAt"] is None
    assert payload["createdAt"] == "2026-07-18T08:30:00Z"
    assert payload["actor"] == {
        "handle": "viewer",
        "firstName": "View",
        "lastName": "Er",
    }


def test_notification_response_rejects_unknown_type_and_action_values():
    base_payload = _notification_response().model_dump()

    with pytest.raises(ValidationError):
        NotificationBaseResponse.model_validate({**base_payload, "type": "unknown.event"})

    with pytest.raises(ValidationError):
        NotificationBaseResponse.model_validate({**base_payload, "available_actions": ["unknown.action"]})


def test_notification_schemas_forbid_extra_fields():
    with pytest.raises(ValidationError):
        NotificationBaseResponse.model_validate({**_notification_response().model_dump(), "metadata": {}})

    with pytest.raises(ValidationError):
        BasicUserSummary.model_validate(
            {"handle": "viewer", "firstName": "View", "lastName": "Er", "email": "private@example.com"}
        )


def test_notification_list_and_mark_all_responses_follow_contract():
    response = NotificationListResponse[NotificationBaseResponse](
        items=[_notification_response()],
        next_cursor="opaque-cursor",
        unread_count=7,
    )
    mark_all = MarkAllNotificationsReadResponse(updated_count=3, unread_count=4)

    assert response.model_dump(mode="json", by_alias=True)["nextCursor"] == "opaque-cursor"
    assert response.model_dump(mode="json", by_alias=True)["unreadCount"] == 7
    assert mark_all.model_dump(mode="json", by_alias=True) == {"updatedCount": 3, "unreadCount": 4}


def test_notification_list_request_defaults_and_limits():
    request = NotificationListRequest()

    assert request.unread_only is False
    assert request.limit == 20
    assert request.cursor is None

    with pytest.raises(ValidationError):
        NotificationListRequest(limit=0)

    with pytest.raises(ValidationError):
        NotificationListRequest(limit=101)


def test_notification_list_request_treats_cursor_as_a_bounded_opaque_string():
    # Signature and scope verification belong to the service, which is the only
    # layer that knows the authenticated recipient the cursor must be bound to.
    assert NotificationListRequest(cursor="not-a-cursor").cursor == "not-a-cursor"

    with pytest.raises(ValidationError):
        NotificationListRequest(cursor="a" * (MAX_CURSOR_LENGTH + 1))
