"""Controller contract tests for the notification inbox."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import app
from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_notification_service
from app.schemas.notification_schemas import (
    MarkAllNotificationsReadResponse,
    NotificationBaseResponse,
    NotificationListResponse,
)
from app.types import NotificationType
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def recipient_id():
    return uuid4()


@pytest.fixture
def notification_response():
    return NotificationBaseResponse(
        id=uuid4(),
        type=NotificationType.FOLLOW_STARTED,
        title="New follower",
        body="Someone followed you.",
        actor=None,
        available_actions=[],
        read_at=None,
        created_at=datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
    )


@pytest.fixture
def notification_service(recipient_id):
    service = AsyncMock()
    app.dependency_overrides[auth_dependency] = lambda: recipient_id
    app.dependency_overrides[get_notification_service] = lambda: service
    yield service
    app.dependency_overrides = {}


def test_list_notifications_uses_aliases_and_returns_common_contract(
    client: TestClient,
    notification_service: AsyncMock,
    recipient_id,
    notification_response,
):
    notification_service.list_notifications.return_value = NotificationListResponse[NotificationBaseResponse](
        items=[notification_response],
        next_cursor="next-page",
        unread_count=5,
    )

    response = client.get("/v1/notifications?unreadOnly=true&limit=10")

    assert response.status_code == 200
    assert response.json()["unreadCount"] == 5
    assert response.json()["items"][0]["availableActions"] == []
    request = notification_service.list_notifications.await_args.args[1]
    assert notification_service.list_notifications.await_args.args[0] == recipient_id
    assert request.unread_only is True
    assert request.limit == 10


@pytest.mark.parametrize("query", ["limit=0", "limit=101", f"cursor={'a' * 513}", "unknown=value"])
def test_list_notifications_rejects_invalid_query(
    query: str,
    client: TestClient,
    notification_service: AsyncMock,
):
    response = client.get(f"/v1/notifications?{query}")

    assert response.status_code == 422
    notification_service.list_notifications.assert_not_awaited()


def test_list_notifications_returns_422_for_a_rejected_cursor(
    client: TestClient,
    notification_service: AsyncMock,
):
    notification_service.list_notifications.side_effect = AppException(ErrorCodes.INVALID_PAGINATION_CURSOR)

    response = client.get("/v1/notifications?cursor=invalid")

    assert response.status_code == 422
    assert response.json()["error_code_name"] == "INVALID_PAGINATION_CURSOR"


def test_list_notifications_requires_authentication(client: TestClient):
    app.dependency_overrides = {}

    response = client.get("/v1/notifications")

    assert response.status_code == 401


def test_mark_notification_read_has_no_request_body_and_returns_response(
    client: TestClient,
    notification_service: AsyncMock,
    recipient_id,
    notification_response,
):
    notification_service.mark_notification_read.return_value = notification_response.model_copy(
        update={"read_at": datetime(2026, 7, 18, 11, 0, tzinfo=UTC)}
    )

    response = client.patch(
        f"/v1/notifications/{notification_response.id}/read",
        headers={"X-CSRF-Token": "csrf"},
        cookies={"__Host-csrf_token": "csrf", "__Host-access_token": "token"},
    )

    assert response.status_code == 200
    assert response.json()["readAt"] == "2026-07-18T11:00:00Z"
    notification_service.mark_notification_read.assert_awaited_once_with(notification_response.id, recipient_id)


def test_mark_notification_read_returns_404_for_foreign_or_missing_id(
    client: TestClient,
    notification_service: AsyncMock,
    notification_response,
):
    notification_service.mark_notification_read.side_effect = AppException(ErrorCodes.NOTIFICATION_NOT_FOUND)

    response = client.patch(
        f"/v1/notifications/{notification_response.id}/read",
        headers={"X-CSRF-Token": "csrf"},
        cookies={"__Host-csrf_token": "csrf", "__Host-access_token": "token"},
    )

    assert response.status_code == 404
    assert response.json()["error_code_name"] == "NOTIFICATION_NOT_FOUND"


def test_mark_all_notifications_read_returns_counts(
    client: TestClient,
    notification_service: AsyncMock,
    recipient_id,
):
    notification_service.mark_all_notifications_read.return_value = MarkAllNotificationsReadResponse(
        updated_count=3,
        unread_count=1,
    )

    response = client.post(
        "/v1/notifications/read-all",
        headers={"X-CSRF-Token": "csrf"},
        cookies={"__Host-csrf_token": "csrf", "__Host-access_token": "token"},
    )

    assert response.status_code == 200
    assert response.json() == {"updatedCount": 3, "unreadCount": 1}
    notification_service.mark_all_notifications_read.assert_awaited_once_with(recipient_id)


def test_notification_mutations_remain_csrf_protected(
    client: TestClient,
    notification_service: AsyncMock,
    notification_response,
):
    response = client.patch(
        f"/v1/notifications/{notification_response.id}/read",
        cookies={"__Host-csrf_token": "csrf", "__Host-access_token": "token"},
    )

    assert response.status_code == 403
    notification_service.mark_notification_read.assert_not_awaited()
