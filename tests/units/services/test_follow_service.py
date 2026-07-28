"""Unit tests for public-profile follow business rules."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.follow_service import FollowService
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
def service(user_repository, follow_repository):
    return FollowService(
        user_repository=user_repository,
        follow_repository=follow_repository,
    )


def _user(*, visibility: str = "public"):
    return SimpleNamespace(id=uuid4(), profile_visibility=visibility)


@pytest.mark.asyncio
async def test_follow_public_target_creates_directional_edge(service, user_repository, follow_repository):
    follower = _user(visibility="private")
    target = _user()
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = target

    await service.follow_user(follower.id, "  TargetUser  ")

    user_repository.find_user_by_handle.assert_awaited_once_with("TargetUser")
    follow_repository.create_follow.assert_awaited_once_with(follower.id, target.id)


@pytest.mark.asyncio
async def test_existing_edge_is_idempotent_after_target_becomes_private(
    service,
    user_repository,
    follow_repository,
):
    follower = _user()
    target = _user(visibility="private")
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = target
    follow_repository.is_following.return_value = True

    await service.follow_user(follower.id, "target")

    follow_repository.create_follow.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", ["private", "followers_only"])
async def test_new_follow_rejects_non_public_target(
    service,
    user_repository,
    follow_repository,
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


@pytest.mark.asyncio
async def test_follow_rejects_self_follow(service, user_repository, follow_repository):
    follower = _user()
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = follower

    with pytest.raises(AppException) as exc_info:
        await service.follow_user(follower.id, "self")

    assert exc_info.value.error is ErrorCodes.SELF_FOLLOW_NOT_ALLOWED
    follow_repository.is_following.assert_not_awaited()
    follow_repository.create_follow.assert_not_awaited()


@pytest.mark.asyncio
async def test_follow_rejects_inactive_follower(service, user_repository, follow_repository):
    user_repository.find_user_by_id.return_value = None

    with pytest.raises(AppException) as exc_info:
        await service.follow_user(uuid4(), "target")

    assert exc_info.value.error is ErrorCodes.USER_NOT_FOUND
    user_repository.find_user_by_handle.assert_not_awaited()
    follow_repository.create_follow.assert_not_awaited()


@pytest.mark.asyncio
async def test_follow_rejects_missing_target(service, user_repository, follow_repository):
    follower = _user()
    user_repository.find_user_by_id.return_value = follower
    user_repository.find_user_by_handle.return_value = None

    with pytest.raises(AppException) as exc_info:
        await service.follow_user(follower.id, "missing")

    assert exc_info.value.error is ErrorCodes.USER_NOT_FOUND
    follow_repository.create_follow.assert_not_awaited()


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
