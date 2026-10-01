"""Unit tests for public-profile follow business rules."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.config.notification_config import FOLLOW_STARTED_NOTIFICATION_COOLDOWN_SECONDS
from app.services.follow_service import FollowService
from app.types import NotificationType
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


@pytest.fixture
def user_repository():
    return AsyncMock()


@pytest.fixture
def follow_repository():
    repository = AsyncMock()
    repository.is_following.return_value = False
    return repository


@pytest.fixture
def notification_service():
    return AsyncMock()


@pytest.fixture
def service(user_repository, follow_repository, notification_service):
    return FollowService(
        user_repository=user_repository,
        follow_repository=follow_repository,
        notification_service=notification_service,
    )


def _user(*, visibility: str = "public", first_name: str = "Ada", last_name: str = "Lovelace"):
    return SimpleNamespace(
        id=uuid4(),
        profile_visibility=visibility,
        first_name=first_name,
        last_name=last_name,
    )


def _assert_follow_started_emitted(notification_service, *, actor, recipient) -> None:
    notification_service.create_notification.assert_awaited_once()
    call = notification_service.create_notification.await_args
    data = call.args[0]
    assert data.recipient_id == recipient.id
    assert data.actor_id == actor.id
    assert data.type is NotificationType.FOLLOW_STARTED
    assert data.title == "New follower"
    assert data.body == f"{actor.first_name} {actor.last_name} started following you."
    assert data.deduplication_key == f"follow.started:{actor.id}:{datetime.now(UTC).strftime('%G-W%V')}"
    assert call.kwargs["cooldown_key"] == f"cinelog:notif:follow-started:{recipient.id}:{actor.id}"
    assert call.kwargs["cooldown_seconds"] == FOLLOW_STARTED_NOTIFICATION_COOLDOWN_SECONDS


@pytest.mark.asyncio
async def test_follow_public_target_creates_directional_edge(
    service,
    user_repository,
    follow_repository,
    notification_service,
):
    follower = _user(visibility="private")
    target = _user()
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = target

    await service.follow_user(follower.id, "  TargetUser  ")

    user_repository.find_user_by_handle.assert_awaited_once_with("TargetUser")
    follow_repository.create_follow.assert_awaited_once_with(follower.id, target.id)
    _assert_follow_started_emitted(notification_service, actor=follower, recipient=target)


@pytest.mark.asyncio
async def test_existing_edge_is_idempotent_after_target_becomes_private(
    service,
    user_repository,
    follow_repository,
    notification_service,
):
    follower = _user()
    target = _user(visibility="private")
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = target
    follow_repository.is_following.return_value = True

    await service.follow_user(follower.id, "target")

    follow_repository.create_follow.assert_not_awaited()
    notification_service.create_notification.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", ["private", "followers_only"])
async def test_new_follow_rejects_non_public_target(
    service,
    user_repository,
    follow_repository,
    notification_service,
    visibility,
):
    follower = _user()
    target = _user(visibility=visibility)
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = target

    with pytest.raises(AppException) as exc_info:
        await service.follow_user(follower.id, "target")

    assert exc_info.value.error is ErrorCodes.PROFILE_NOT_PUBLIC
    follow_repository.create_follow.assert_not_awaited()
    notification_service.create_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_follow_rejects_self_follow(service, user_repository, follow_repository, notification_service):
    follower = _user()
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = follower

    with pytest.raises(AppException) as exc_info:
        await service.follow_user(follower.id, "self")

    assert exc_info.value.error is ErrorCodes.SELF_FOLLOW_NOT_ALLOWED
    follow_repository.is_following.assert_not_awaited()
    follow_repository.create_follow.assert_not_awaited()
    notification_service.create_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_follow_rejects_inactive_follower(service, user_repository, follow_repository, notification_service):
    user_repository.find_user_by_id.return_value = None

    with pytest.raises(AppException) as exc_info:
        await service.follow_user(uuid4(), "target")

    assert exc_info.value.error is ErrorCodes.USER_NOT_FOUND
    user_repository.find_user_by_handle.assert_not_awaited()
    follow_repository.create_follow.assert_not_awaited()
    notification_service.create_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_follow_rejects_missing_target(service, user_repository, follow_repository, notification_service):
    follower = _user()
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = None

    with pytest.raises(AppException) as exc_info:
        await service.follow_user(follower.id, "missing")

    assert exc_info.value.error is ErrorCodes.USER_NOT_FOUND
    follow_repository.create_follow.assert_not_awaited()
    notification_service.create_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_follow_swallows_notification_emission_failure(
    service,
    user_repository,
    follow_repository,
    notification_service,
):
    follower = _user()
    target = _user()
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = target
    notification_service.create_notification.side_effect = RuntimeError("redis down")

    await service.follow_user(follower.id, "target")

    follow_repository.create_follow.assert_awaited_once_with(follower.id, target.id)


@pytest.mark.asyncio
async def test_unfollow_deletes_edge_regardless_of_visibility(service, user_repository, follow_repository):
    follower = _user()
    target = _user(visibility="followers_only")
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = target

    await service.unfollow_user(follower.id, "target")

    follow_repository.delete_follow.assert_awaited_once_with(follower.id, target.id)


@pytest.mark.asyncio
async def test_unfollow_rejects_inactive_follower(service, user_repository, follow_repository):
    user_repository.find_user_by_id.return_value = None

    with pytest.raises(AppException) as exc_info:
        await service.unfollow_user(uuid4(), "target")

    assert exc_info.value.error is ErrorCodes.USER_NOT_FOUND
    user_repository.find_user_by_handle.assert_not_awaited()
    follow_repository.delete_follow.assert_not_awaited()


@pytest.mark.asyncio
async def test_unfollow_rejects_missing_target(service, user_repository, follow_repository):
    follower = _user()
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = None

    with pytest.raises(AppException) as exc_info:
        await service.unfollow_user(follower.id, "missing")

    assert exc_info.value.error is ErrorCodes.USER_NOT_FOUND
    follow_repository.delete_follow.assert_not_awaited()
