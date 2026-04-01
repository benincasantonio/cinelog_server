from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, Request
from app.repository.log_repository import LogRepository
from app.schemas.log_schemas import (
    LogCreateRequest,
    LogCreateResponse,
    LogUpdateRequest,
    LogListRequest,
    LogListResponse,
)
from app.services.log_service import LogService
from app.dependencies.auth_dependency import auth_dependency

router = APIRouter()

log_repository = LogRepository()
log_service = LogService(log_repository)


@router.post("/", response_model=LogCreateResponse, status_code=201)
async def create_log(
    request_body: LogCreateRequest,
    request: Request,
    user_id: PydanticObjectId = Depends(auth_dependency),
) -> LogCreateResponse:
    """
    Create a new viewing log entry.

    Requires authentication via Cookie token.
    """
    return await log_service.create_log(user_id=user_id, request=request_body)


@router.put("/{log_id}", response_model=LogCreateResponse)
async def update_log(
    log_id: str,
    request_body: LogUpdateRequest,
    request: Request,
    user_id: PydanticObjectId = Depends(auth_dependency),
) -> LogCreateResponse:
    """
    Update an existing viewing log entry.

    Requires authentication via Cookie token.
    Only the owner of the log can update it.
    """
    return await log_service.update_log(
        user_id=user_id, log_id=log_id, request=request_body
    )


@router.get("/{handle}", response_model=LogListResponse)
async def get_logs_by_handle(
    handle: str,
    request: Request,
    list_request: LogListRequest = Depends(),
    user_id: PydanticObjectId = Depends(auth_dependency),
) -> LogListResponse:
    """
    Get list of a user's viewing logs by handle.

    Requires authentication via Cookie token.
    Returns logs if the profile is public or the requester is the owner.
    Returns 403 if the profile is not public and the requester is not the owner.
    """
    return await log_service.get_user_logs_by_handle(
        handle=handle, requester_id=user_id, request=list_request
    )
