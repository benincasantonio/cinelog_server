from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from app.config.rate_limiter import limiter
from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_follow_service, get_user_service
from app.schemas.user_schemas import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    UpdateProfileRequest,
    UserProfileResponse,
    UserResponse,
)
from app.services.follow_service import FollowService
from app.services.user_service import UserService

router = APIRouter()


@router.get("/info", response_model=UserResponse)
async def get_user_info(
    request: Request,
    user_id: UUID = Depends(auth_dependency),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    return await user_service.get_user_info(user_id)


@router.get("/{handle}/profile", response_model=UserProfileResponse)
async def get_public_profile(
    handle: str,
    request: Request,
    user_id: UUID = Depends(auth_dependency),
    user_service: UserService = Depends(get_user_service),
) -> UserProfileResponse:
    return await user_service.get_visible_profile(handle=handle, requester_id=user_id)


@router.put(
    "/{handle}/follow",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
@limiter.limit("60/minute")
async def follow_user(
    handle: str,
    request: Request,
    response: Response,
    user_id: UUID = Depends(auth_dependency),
    follow_service: FollowService = Depends(get_follow_service),
) -> None:
    """Idempotently follow an active public profile."""

    await follow_service.follow_user(follower_id=user_id, handle=handle)


@router.delete(
    "/{handle}/follow",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
@limiter.limit("60/minute")
async def unfollow_user(
    handle: str,
    request: Request,
    response: Response,
    user_id: UUID = Depends(auth_dependency),
    follow_service: FollowService = Depends(get_follow_service),
) -> None:
    """Idempotently unfollow an active profile."""

    await follow_service.unfollow_user(follower_id=user_id, handle=handle)


@router.put("/settings/profile", response_model=UserResponse)
async def update_profile(
    request_body: UpdateProfileRequest,
    request: Request,
    user_id: UUID = Depends(auth_dependency),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    return await user_service.update_profile(user_id, request_body)


@router.put("/settings/password", response_model=ChangePasswordResponse)
async def change_password(
    request_body: ChangePasswordRequest,
    request: Request,
    user_id: UUID = Depends(auth_dependency),
    user_service: UserService = Depends(get_user_service),
) -> ChangePasswordResponse:
    return await user_service.change_password(
        user_id=user_id,
        current_password=request_body.current_password,
        new_password=request_body.new_password,
    )
