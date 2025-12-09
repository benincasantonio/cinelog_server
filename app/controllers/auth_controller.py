from fastapi import APIRouter

from app.repository.user_repository import UserRepository
from app.repository.firebase_auth_repository import FirebaseAuthRepository
from app.schemas.auth_schemas import (
    RegisterRequest,
    RegisterResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()

user_repository = UserRepository()
firebase_auth_repository = FirebaseAuthRepository()
auth_service = AuthService(user_repository, firebase_auth_repository)


@router.post("/register")
async def register(request: RegisterRequest) -> RegisterResponse:
    """
    Handle user registration.
    """
    return auth_service.register(request=request)
