from fastapi import APIRouter, Request

from app.repository.user_repository import UserRepository
from app.schemas.auth_schemas import LoginRequest, RegisterRequest, RegisterResponse, LoginResponse
from app.services.auth_service import AuthService
from app.utils.exceptions import AppException

router = APIRouter()

user_repository = UserRepository()
auth_service = AuthService(user_repository)

@router.post("/login")
def login(request: LoginRequest) -> LoginResponse:
    """
    Handle user login.
    """
    try:
        return auth_service.login(request=request)
    except AppException as e:
        raise e

@router.post("/register")
async def register(request: Request) -> RegisterResponse:
    """
    Handle user registration.
    """
    request_data = await request.json()

    register_request: RegisterRequest = RegisterRequest(
        firstName=request_data["firstName"],
        lastName=request_data["lastName"],
        email=request_data["email"],
        handle=request_data["handle"],
        password=request_data["password"],
        dateOfBirth=request_data["dateOfBirth"]
    )

    try:
        return auth_service.register(request=register_request)
    except AppException as e:
        raise e
