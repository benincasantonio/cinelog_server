from app.repository.user_repository import UserRepository
from app.schemas.auth_schemas import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse
from app.utils.error_codes import ErrorCodes
from app.utils.exceptions import AppException
from app.utils.generate_access_token import generate_access_token
from app.utils.hash_password_utils import check_password, hash_password

class AuthService():
    user_repository: UserRepository

    def __init__(self, user_repository):
        self.user_repository = user_repository

    def login(self, request: LoginRequest) -> LoginResponse:        
        user = self.user_repository.find_user_by_email_or_handle(request.emailOrHandle.strip())

        if not user:
            raise AppException(ErrorCodes.INVALID_EMAIL_OR_PASSWORD)

        if not check_password(request.password, user.password):
            raise AppException(ErrorCodes.INVALID_EMAIL_OR_PASSWORD)
        
        jwt_token = generate_access_token(user_id=user.id.__str__())

        response: LoginResponse = LoginResponse(
            access_token=jwt_token,
            user_id=user.id.__str__(),
            firstName=user.firstName,
            lastName=user.lastName,
            email=user.email,
            handle=user.handle
        )

        return response



    def register(self, request: RegisterRequest):
        request.password = hash_password(request.password.strip())
        user = self.user_repository.create_user(request=request)

        jwt_token = generate_access_token(user_id=user.id.__str__())

        response: RegisterResponse = RegisterResponse(
            access_token=jwt_token,
            email=request.email,
            firstName=request.firstName,
            lastName=request.lastName,
            handle=request.handle,
            user_id=user.id.__str__(),
        )

        return response
