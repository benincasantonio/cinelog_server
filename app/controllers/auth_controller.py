from fastapi import APIRouter

from app.repository.user_repository import UserRepository
from app.schemas.auth_schemas import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    LoginResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()

user_repository = UserRepository()
auth_service = AuthService(user_repository)


@router.post("/login")
def login(request: LoginRequest) -> LoginResponse:
    """
    Handle user login.
    """
    return auth_service.login(request=request)


@router.post("/register")
async def register(request: RegisterRequest) -> RegisterResponse:
    """
    Handle user registration.
    """
    return auth_service.register(request=request)
