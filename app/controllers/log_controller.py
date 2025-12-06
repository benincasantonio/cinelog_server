from fastapi import APIRouter, Depends, Request, HTTPException
import jwt
import os

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


def get_user_id_from_token(request: Request) -> str:
    """Extract user ID from JWT token in request headers."""
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        secret_key = os.getenv("JWT_SECRET_KEY")
        algorithm = "HS256"
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


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
    user_id = get_user_id_from_token(request)
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
    user_id = get_user_id_from_token(request)
    return log_service.update_log(user_id=user_id, log_id=log_id, request=request_body)


@router.get("/", response_model=LogListResponse)
def get_logs(
    request: Request,
    sortBy: str = "dateWatched",
    sortOrder: str = "desc",
    watchedWhere: str = None,
    dateWatchedFrom: str = None,
    dateWatchedTo: str = None,
    _: bool = Depends(auth_dependency)
) -> LogListResponse:
    """
    Get list of user's viewing logs.

    Requires authentication via Bearer token.
    Returns all logs filtered and sorted according to query parameters.
    """
    user_id = get_user_id_from_token(request)

    # Build request object from query parameters
    list_request = LogListRequest(
        sortBy=sortBy,
        sortOrder=sortOrder,
        watchedWhere=watchedWhere,
        dateWatchedFrom=dateWatchedFrom,
        dateWatchedTo=dateWatchedTo
    )

    return log_service.get_user_logs(user_id=user_id, request=list_request)
