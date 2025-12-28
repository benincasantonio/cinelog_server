from fastapi import APIRouter, Depends, Request, HTTPException

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
from app.utils.access_token_utils import get_user_id_from_token

router = APIRouter()

log_repository = LogRepository()
log_service = LogService(log_repository)


@router.post("/", response_model=LogCreateResponse)
def create_log(
    request_body: LogCreateRequest,
    request: Request,
    _: bool = Depends(auth_dependency)
) -> LogCreateResponse:
    """
    Create a new viewing log entry.

    Requires authentication via Bearer token.
    """
    token = request.headers.get("Authorization")
    try:
        user_id = get_user_id_from_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    return log_service.create_log(user_id=user_id, request=request_body)


@router.put("/{log_id}", response_model=LogCreateResponse)
def update_log(
    log_id: str,
    request_body: LogUpdateRequest,
    request: Request,
    _: bool = Depends(auth_dependency)
) -> LogCreateResponse:
    """
    Update an existing viewing log entry.

    Requires authentication via Bearer token.
    Only the owner of the log can update it.
    """
    token = request.headers.get("Authorization")
    try:
        user_id = get_user_id_from_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    return log_service.update_log(user_id=user_id, log_id=log_id, request=request_body)


@router.get("/", response_model=LogListResponse)
def get_logs(
    request: Request,
    list_request: LogListRequest = Depends(),
    _: bool = Depends(auth_dependency)
) -> LogListResponse:
    """
    Get list of user's viewing logs.

    Requires authentication via Bearer token.
    Returns all logs filtered and sorted according to query parameters.
    """
    token = request.headers.get("Authorization")
    try:
        user_id = get_user_id_from_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    return log_service.get_user_logs(user_id=user_id, request=list_request)
