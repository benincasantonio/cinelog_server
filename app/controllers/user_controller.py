from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, Request

from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_user_service
from app.schemas.user_schemas import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    UpdateProfileRequest,
    UserProfileResponse,
    UserResponse,
)
from app.services.user_service import UserService

router = APIRouter()


@router.get("/info", response_model=UserResponse)
async def get_user_info(
    request: Request,
    user_id: PydanticObjectId = Depends(auth_dependency),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    return await user_service.get_user_info(user_id)


@router.get("/{handle}/profile", response_model=UserProfileResponse)
async def get_public_profile(
    handle: str,
    request: Request,
    user_id: PydanticObjectId = Depends(auth_dependency),
    user_service: UserService = Depends(get_user_service),
) -> UserProfileResponse:
    return await user_service.get_visible_profile(handle=handle, requester_id=user_id)


@router.put("/settings/profile", response_model=UserResponse)
async def update_profile(
    request_body: UpdateProfileRequest,
    request: Request,
    user_id: PydanticObjectId = Depends(auth_dependency),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    return await user_service.update_profile(user_id, request_body)


@router.put("/settings/password", response_model=ChangePasswordResponse)
async def change_password(
    request_body: ChangePasswordRequest,
    request: Request,
    user_id: PydanticObjectId = Depends(auth_dependency),
    user_service: UserService = Depends(get_user_service),
) -> ChangePasswordResponse:
    return await user_service.change_password(
        user_id=user_id,
        current_password=request_body.current_password,
        new_password=request_body.new_password,
    )
