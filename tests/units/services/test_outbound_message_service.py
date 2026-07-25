"""Unit tests for the outbound-message enqueue service (repository + renderers only)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.notification_model import Notification
from app.services import outbound_email_renderer
from app.services.outbound_message_service import OutboundMessageService
from app.types import NotificationType, OutboundMessageChannel, OutboundMessageKind


@pytest.fixture
def outbound_message_repository():
    repository = AsyncMock()
    repository.enqueue.return_value = uuid4()
    return repository


@pytest.fixture
def user_repository():
    return AsyncMock()


@pytest.fixture
def service(outbound_message_repository, user_repository):
    return OutboundMessageService(outbound_message_repository, user_repository)


@pytest.mark.asyncio
async def test_enqueue_notification_email_renders_and_writes_expected_row(
    service: OutboundMessageService,
    outbound_message_repository: AsyncMock,
    user_repository: AsyncMock,
):
    recipient_id = uuid4()
    user_repository.find_user_by_id.return_value = SimpleNamespace(email="recipient@example.com")
    notification = Notification(
        id=uuid4(),
        recipient_id=recipient_id,
        type=NotificationType.FOLLOW_STARTED.value,
        title="New follower",
        body="A user started following you.",
    )

    result = await service.enqueue_notification_email(notification)

    assert result is not None
    user_repository.find_user_by_id.assert_awaited_once_with(recipient_id)
    outbound_message_repository.enqueue.assert_awaited_once()
    args, kwargs = outbound_message_repository.enqueue.call_args
    written = args[0]
    assert written.kind is OutboundMessageKind.NOTIFICATION
    assert written.notification_id == notification.id
    assert written.channel is OutboundMessageChannel.EMAIL
    assert written.destination == "recipient@example.com"
    assert written.subject == "New follower"
    assert written.text_body == "A user started following you."
    assert kwargs.get("session") is None


@pytest.mark.asyncio
async def test_enqueue_notification_email_forwards_the_caller_session(
    service: OutboundMessageService,
    outbound_message_repository: AsyncMock,
    user_repository: AsyncMock,
):
    user_repository.find_user_by_id.return_value = SimpleNamespace(email="recipient@example.com")
    notification = Notification(
        id=uuid4(),
        recipient_id=uuid4(),
        type=NotificationType.FOLLOW_STARTED.value,
        title="New follower",
        body="A user started following you.",
    )
    sentinel_session = object()

    await service.enqueue_notification_email(notification, session=sentinel_session)  # type: ignore[arg-type]

    _, kwargs = outbound_message_repository.enqueue.call_args
    assert kwargs["session"] is sentinel_session


@pytest.mark.asyncio
async def test_enqueue_notification_email_raises_when_recipient_not_found(
    service: OutboundMessageService,
    user_repository: AsyncMock,
    outbound_message_repository: AsyncMock,
):
    user_repository.find_user_by_id.return_value = None
    notification = Notification(
        id=uuid4(),
        recipient_id=uuid4(),
        type=NotificationType.FOLLOW_STARTED.value,
        title="Title",
        body="Body",
    )

    with pytest.raises(ValueError, match="was not found"):
        await service.enqueue_notification_email(notification)

    outbound_message_repository.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_enqueue_notification_email_raises_for_an_unregistered_notification_type(
    service: OutboundMessageService,
    user_repository: AsyncMock,
    outbound_message_repository: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delitem(outbound_email_renderer._NOTIFICATION_RENDERERS, NotificationType.FOLLOW_ACCEPTED)
    notification = Notification(
        id=uuid4(),
        recipient_id=uuid4(),
        type=NotificationType.FOLLOW_ACCEPTED.value,
        title="Title",
        body="Body",
    )

    with pytest.raises(ValueError, match="No email renderer registered"):
        await service.enqueue_notification_email(notification)

    user_repository.find_user_by_id.assert_not_awaited()
    outbound_message_repository.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_enqueue_registration_verification_writes_expected_row(
    service: OutboundMessageService,
    outbound_message_repository: AsyncMock,
):
    result = await service.enqueue_registration_verification("user@example.com", "ABC123")

    assert result is not None
    args, _ = outbound_message_repository.enqueue.call_args
    written = args[0]
    assert written.kind is OutboundMessageKind.REGISTRATION_VERIFICATION
    assert written.notification_id is None
    assert written.channel is OutboundMessageChannel.EMAIL
    assert written.destination == "user@example.com"
    assert written.subject == "Verify your Cinelog email"
    assert "ABC123" in written.text_body


@pytest.mark.asyncio
async def test_enqueue_registration_existing_account_writes_expected_row(
    service: OutboundMessageService,
    outbound_message_repository: AsyncMock,
):
    result = await service.enqueue_registration_existing_account("user@example.com")

    assert result is not None
    args, _ = outbound_message_repository.enqueue.call_args
    written = args[0]
    assert written.kind is OutboundMessageKind.REGISTRATION_EXISTING_ACCOUNT
    assert written.notification_id is None
    assert written.destination == "user@example.com"
    assert written.subject == "Cinelog account already exists"


@pytest.mark.asyncio
async def test_enqueue_password_reset_writes_expected_row(
    service: OutboundMessageService,
    outbound_message_repository: AsyncMock,
):
    result = await service.enqueue_password_reset("user@example.com", "XYZ987")

    assert result is not None
    args, _ = outbound_message_repository.enqueue.call_args
    written = args[0]
    assert written.kind is OutboundMessageKind.PASSWORD_RESET
    assert written.notification_id is None
    assert written.destination == "user@example.com"
    assert written.subject == "Password Reset - Cinelog"
    assert "XYZ987" in written.text_body
