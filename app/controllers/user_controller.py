from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, Request
from app.services.user_service import UserService
from app.services.log_service import LogService
from app.repository.user_repository import UserRepository
from app.repository.log_repository import LogRepository
from app.dependencies.auth_dependency import auth_dependency
from app.schemas.user_schemas import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    PublicProfileResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.schemas.log_schemas import LogListResponse, LogListRequest

router = APIRouter()

user_repository = UserRepository()
log_repository = LogRepository()
user_service = UserService(user_repository, log_repository)

log_service = LogService(log_repository)


@router.get("/info", response_model=UserResponse)
async def get_user_info(
    request: Request, user_id: PydanticObjectId = Depends(auth_dependency)
) -> UserResponse:
    """
    Get current user information from MongoDB.

    Requires authentication via Cookie token.
    """
    return await user_service.get_user_info(user_id)


@router.get("/handle/{handle}", response_model=PublicProfileResponse)
async def get_public_profile(
    handle: str,
    request: Request,
    requesting_user_id: PydanticObjectId = Depends(auth_dependency),
) -> PublicProfileResponse:
    """
    Get a user's public profile by handle.

    Requires authentication via Cookie token.
    Visibility rules:
    - Own profile: always full access.
    - Public: full profile accessible.
    - friends_only / private: basic info only (name, handle, bio).
    """
    return await user_service.get_public_profile(handle, requesting_user_id)


@router.get("/handle/{handle}/logs", response_model=LogListResponse)
async def get_public_user_logs(
    handle: str,
    request: Request,
    list_request: LogListRequest = Depends(),
    requesting_user_id: PydanticObjectId = Depends(auth_dependency),
) -> LogListResponse:
    """
    Get a user's viewing logs by handle, enforcing visibility rules.

    Requires authentication via Cookie token.
    Visibility rules:
    - Own profile: always full access.
    - Public: logs accessible.
    - friends_only / private: 403 PROFILE_NOT_PUBLIC.
    """
    return await user_service.get_public_user_logs(
        handle, requesting_user_id, list_request
    )


@router.put("/settings/profile", response_model=UserResponse)
async def update_profile(
    request_body: UpdateProfileRequest,
    request: Request,
    user_id: PydanticObjectId = Depends(auth_dependency),
) -> UserResponse:
    """
    Update current user profile.

    Requires authentication via Cookie token.
    Only provided fields will be updated.
    """
    return await user_service.update_profile(user_id, request_body)


@router.put("/settings/password", response_model=ChangePasswordResponse)
async def change_password(
    request_body: ChangePasswordRequest,
    request: Request,
    user_id: PydanticObjectId = Depends(auth_dependency),
) -> ChangePasswordResponse:
    """
    Change current user password.

    Requires authentication via Cookie token.
    """
    return await user_service.change_password(
        user_id=user_id,
        current_password=request_body.current_password,
        new_password=request_body.new_password,
    )


@router.get("/{user_id}/logs", response_model=LogListResponse)
async def get_user_logs(
    user_id: PydanticObjectId,
    list_request: LogListRequest = Depends(),
    _: PydanticObjectId = Depends(auth_dependency),
) -> LogListResponse:
    """
    Get list of a specific user's viewing logs.

    Requires authentication via Cookie token.
    Returns all logs filtered and sorted according to query parameters.
    """
    return await log_service.get_user_logs(user_id=user_id, request=list_request)
