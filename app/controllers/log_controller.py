from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, Request, Response, status

from app.config.rate_limiter import limiter
from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_log_service
from app.schemas.log_schemas import (
    LogCreateRequest,
    LogCreateResponse,
    LogListRequest,
    LogListResponse,
    LogUpdateRequest,
)
from app.services.log_service import LogService

router = APIRouter()


@router.post("/", response_model=LogCreateResponse, status_code=201)
@limiter.limit("20/minute")
async def create_log(
    request: Request,
    response: Response,
    request_body: LogCreateRequest,
    user_id: PydanticObjectId = Depends(auth_dependency),
    log_service: LogService = Depends(get_log_service),
) -> LogCreateResponse:
    """
    Create a new viewing log entry.

    Requires authentication via Cookie token.
    """
    return await log_service.create_log(user_id=user_id, request=request_body)


@router.put("/{log_id}", response_model=LogCreateResponse)
@limiter.limit("10/minute")
async def update_log(
    request: Request,
    response: Response,
    log_id: str,
    request_body: LogUpdateRequest,
    user_id: PydanticObjectId = Depends(auth_dependency),
    log_service: LogService = Depends(get_log_service),
) -> LogCreateResponse:
    """
    Update an existing viewing log entry.

    Requires authentication via Cookie token.
    Only the owner of the log can update it.
    """
    return await log_service.update_log(user_id=user_id, log_id=log_id, request=request_body)


@router.delete(
    "/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
@limiter.limit("20/minute")
async def delete_log(
    request: Request,
    response: Response,
    log_id: str,
    user_id: PydanticObjectId = Depends(auth_dependency),
    log_service: LogService = Depends(get_log_service),
) -> None:
    """
    Delete a viewing log entry.

    Requires authentication via Cookie token.
    Only the owner of the log can delete it.
    """
    await log_service.delete_log(user_id=user_id, log_id=log_id)


@router.get("/{handle}", response_model=LogListResponse)
async def get_logs_by_handle(
    handle: str,
    request: Request,
    list_request: LogListRequest = Depends(),
    user_id: PydanticObjectId = Depends(auth_dependency),
    log_service: LogService = Depends(get_log_service),
) -> LogListResponse:
    """
    Get list of a user's viewing logs by handle.

    Requires authentication via Cookie token.
    Returns logs if the profile is public or the requester is the owner.
    Returns 403 if the profile is not public and the requester is not the owner.
    """
    return await log_service.get_user_logs_by_handle(handle=handle, requester_id=user_id, request=list_request)
