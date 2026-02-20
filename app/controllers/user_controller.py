from fastapi import APIRouter, Depends, Request, HTTPException
from app.services.user_service import UserService
from app.services.log_service import LogService
from app.repository.user_repository import UserRepository
from app.repository.log_repository import LogRepository
from app.dependencies.auth_dependency import auth_dependency
from app.schemas.user_schemas import UserResponse
from app.schemas.log_schemas import LogListResponse, LogListRequest

router = APIRouter()

user_repository = UserRepository()
user_service = UserService(user_repository)

log_repository = LogRepository()
log_service = LogService(log_repository)

@router.get("/info", response_model=UserResponse)
def get_user_info(
    request: Request,
    user_id: str = Depends(auth_dependency)
) -> UserResponse:
    """
    Get current user information from MongoDB.
    
    Requires authentication via Cookie token.
    """
    return user_service.get_user_info(user_id)


@router.get("/{user_id}/logs", response_model=LogListResponse)
def get_user_logs(
    user_id: str,
    list_request: LogListRequest = Depends(),
    _: bool = Depends(auth_dependency)
) -> LogListResponse:
    """
    Get list of a specific user's viewing logs.

    Requires authentication via Cookie token.
    Returns all logs filtered and sorted according to query parameters.
    """
    return log_service.get_user_logs(user_id=user_id, request=list_request)
