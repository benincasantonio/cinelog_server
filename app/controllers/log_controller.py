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
def create_log(
    request_body: LogCreateRequest,
    request: Request,
    user_id: str = Depends(auth_dependency),
) -> LogCreateResponse:
    """
    Create a new viewing log entry.

    Requires authentication via Cookie token.
    """
    return log_service.create_log(user_id=user_id, request=request_body)


@router.put("/{log_id}", response_model=LogCreateResponse)
def update_log(
    log_id: str,
    request_body: LogUpdateRequest,
    request: Request,
    user_id: str = Depends(auth_dependency),
) -> LogCreateResponse:
    """
    Update an existing viewing log entry.

    Requires authentication via Cookie token.
    Only the owner of the log can update it.
    """
    return log_service.update_log(user_id=user_id, log_id=log_id, request=request_body)


@router.get("/", response_model=LogListResponse)
def get_logs(
    request: Request,
    list_request: LogListRequest = Depends(),
    user_id: str = Depends(auth_dependency),
) -> LogListResponse:
    """
    Get list of user's viewing logs.

    Requires authentication via Cookie token.
    Returns all logs filtered and sorted according to query parameters.
    """
    return log_service.get_user_logs(user_id=user_id, request=list_request)
