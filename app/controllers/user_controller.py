from fastapi import APIRouter, Depends, Request, HTTPException
from app.services.user_service import UserService
from app.repository.user_repository import UserRepository
from app.repository.firebase_auth_repository import FirebaseAuthRepository
from app.dependencies.auth_dependency import auth_dependency
from app.utils.access_token_utils import get_user_id_from_token
from app.schemas.user_schemas import UserResponse

router = APIRouter()

user_repository = UserRepository()
firebase_auth_repository = FirebaseAuthRepository()
user_service = UserService(user_repository, firebase_auth_repository)

@router.get("/info", response_model=UserResponse)
def get_user_info(
    request: Request,
    _: bool = Depends(auth_dependency)
) -> UserResponse:
    """
    Get current user information from MongoDB and Firebase.
    
    Requires authentication via Bearer token.
    """
    token = request.headers.get("Authorization")
    try:
        user_id = get_user_id_from_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
        
    return user_service.get_user_info(user_id)
