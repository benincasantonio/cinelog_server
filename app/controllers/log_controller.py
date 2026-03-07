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
from app.utils.object_id_utils import to_object_id


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


@router.get("/", response_model=LogListResponse)
async def get_logs(
    request: Request,
    list_request: LogListRequest = Depends(),
    user_id: str = Depends(auth_dependency),
) -> LogListResponse:
    """
    Get list of user's viewing logs.

    Requires authentication via Cookie token.
    Returns all logs filtered and sorted according to query parameters.
    """

    id = to_object_id(user_id)

    if id is None:
        # This should not happen if auth_dependency is working correctly
        raise ValueError("Invalid user_id")

    return await log_service.get_user_logs(user_id=id, request=list_request)
