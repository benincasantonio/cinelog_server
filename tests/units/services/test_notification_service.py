"""Unit tests for notification inbox business logic."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.config.notification_config import notification_list_cursor_scope
from app.repository.notification_repository_protocol import (
    MarkAllNotificationsReadResult,
    NotificationCreateResult,
    NotificationPage,
)
from app.schemas.notification_schemas import (
    NotificationCreateData,
    NotificationListRequest,
)
from app.services.notification_service import NotificationService
from app.types import NotificationType, TimestampUUIDCursor
from app.utils.cursor_pagination_utils import (
    decode_timestamp_uuid_cursor,
    encode_timestamp_uuid_cursor,
)
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


def _notification(*, actor=None, read_at=None):
    return SimpleNamespace(
        id=uuid4(),
        type=NotificationType.FOLLOW_STARTED.value,
        title="Title",
        body="Body",
        actor=actor,
        read_at=read_at,
        created_at=datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
    )


@pytest.fixture
def repository():
    return AsyncMock()


@pytest.fixture
def service(repository):
    return NotificationService(repository=repository)


@pytest.mark.asyncio
async def test_list_notifications_decodes_cursor_assembles_page_and_encodes_next_cursor(
    service: NotificationService,
    repository: AsyncMock,
):
    recipient_id = uuid4()
    prior_cursor = TimestampUUIDCursor(timestamp=datetime(2026, 7, 18, 11, 0, tzinfo=UTC), id=uuid4())

    request = NotificationListRequest(
        cursor=encode_timestamp_uuid_cursor(prior_cursor, scope=notification_list_cursor_scope(recipient_id)),
        limit=2,
        unread_only=True,
    )
    first = _notification()
    second = _notification()
    page = NotificationPage(items=[first, second], has_more=True, unread_count=9)
    repository.list_notifications.return_value = page

    response = await service.list_notifications(recipient_id, request)

    repository.list_notifications.assert_awaited_once_with(
        recipient_id,
        unread_only=True,
        limit=2,
        cursor=prior_cursor,
    )
    assert [item.id for item in response.items] == [first.id, second.id]
    assert all(item.type is NotificationType.FOLLOW_STARTED for item in response.items)
    assert all(item.available_actions == [] for item in response.items)
    assert response.unread_count == 9
    assert response.next_cursor is not None
    assert decode_timestamp_uuid_cursor(
        response.next_cursor,
        expected_scope=notification_list_cursor_scope(recipient_id),
    ) == TimestampUUIDCursor(
        timestamp=second.created_at,
        id=second.id,
    )


@pytest.mark.asyncio
async def test_list_notifications_omits_cursor_when_page_has_no_more_rows(
    service: NotificationService,
    repository: AsyncMock,
):
    recipient_id = uuid4()
    item = _notification()
    repository.list_notifications.return_value = NotificationPage(items=[item], has_more=False, unread_count=1)

    response = await service.list_notifications(recipient_id, NotificationListRequest())

    assert response.next_cursor is None


@pytest.mark.asyncio
async def test_list_notifications_maps_active_actor_and_hides_deleted_actor(
    service: NotificationService,
    repository: AsyncMock,
):
    active_actor = SimpleNamespace(handle="active", first_name="Act", last_name="Ive", deleted=False)
    deleted_actor = SimpleNamespace(handle="deleted", first_name="Del", last_name="Eted", deleted=True)
    active_notification = _notification(actor=active_actor)
    deleted_notification = _notification(actor=deleted_actor)
    repository.list_notifications.return_value = NotificationPage(
        items=[active_notification, deleted_notification],
        has_more=False,
        unread_count=2,
    )

    response = await service.list_notifications(uuid4(), NotificationListRequest())

    assert response.items[0].actor is not None
    assert response.items[0].actor.handle == "active"
    assert response.items[1].actor is None


@pytest.mark.asyncio
async def test_list_notifications_rejects_a_cursor_signed_for_another_recipient(
    service: NotificationService,
    repository: AsyncMock,
):
    other_recipient_id = uuid4()
    foreign_cursor = encode_timestamp_uuid_cursor(
        TimestampUUIDCursor(timestamp=datetime(2026, 7, 18, 11, 0, tzinfo=UTC), id=uuid4()),
        scope=notification_list_cursor_scope(other_recipient_id),
    )

    with pytest.raises(AppException) as exc_info:
        await service.list_notifications(uuid4(), NotificationListRequest(cursor=foreign_cursor))

    assert exc_info.value.error is ErrorCodes.INVALID_PAGINATION_CURSOR
    repository.list_notifications.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_notifications_rejects_a_malformed_cursor_with_the_api_error_contract(
    service: NotificationService,
    repository: AsyncMock,
):
    with pytest.raises(AppException) as exc_info:
        await service.list_notifications(uuid4(), NotificationListRequest(cursor="not-a-cursor"))

    assert exc_info.value.error is ErrorCodes.INVALID_PAGINATION_CURSOR
    assert exc_info.value.error.error_code == 422
    repository.list_notifications.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_notification_delegates_typed_internal_input(
    service: NotificationService,
    repository: AsyncMock,
):
    data = NotificationCreateData(
        recipient_id=uuid4(),
        type=NotificationType.FOLLOW_STARTED,
        title="Title",
        body="Body",
    )
    expected = NotificationCreateResult(notification=_notification(), created=True)
    repository.create_notification.return_value = expected

    assert await service.create_notification(data) is expected
    repository.create_notification.assert_awaited_once_with(data)


@pytest.mark.asyncio
async def test_mark_notification_read_returns_mapped_response(
    service: NotificationService,
    repository: AsyncMock,
):
    recipient_id = uuid4()
    notification = _notification(read_at=datetime.now(UTC))
    repository.mark_notification_read.return_value = notification

    response = await service.mark_notification_read(notification.id, recipient_id)

    assert response.id == notification.id
    assert response.type is NotificationType.FOLLOW_STARTED
    assert response.read_at == notification.read_at
    assert response.available_actions == []


@pytest.mark.asyncio
async def test_mark_notification_read_hides_missing_or_foreign_rows(
    service: NotificationService,
    repository: AsyncMock,
):
    repository.mark_notification_read.return_value = None

    with pytest.raises(AppException) as exc_info:
        await service.mark_notification_read(uuid4(), uuid4())

    assert exc_info.value.error is ErrorCodes.NOTIFICATION_NOT_FOUND


@pytest.mark.asyncio
async def test_mark_all_notifications_read_maps_repository_result(
    service: NotificationService,
    repository: AsyncMock,
):
    repository.mark_all_notifications_read.return_value = MarkAllNotificationsReadResult(
        updated_count=4,
        unread_count=1,
    )

    response = await service.mark_all_notifications_read(uuid4())

    assert response.updated_count == 4
    assert response.unread_count == 1
