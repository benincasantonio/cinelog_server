from app.repository.user_repository import UserRepository
from app.schemas.auth_schemas import RegisterRequest, RegisterResponse
from app.utils import generate_access_token

class AuthService():
    user_repository = UserRepository()

    def __init__(self, user_repository, token_service):
        self.user_repository = user_repository
        self.token_service = token_service

    def login(self, username, password):
        raise NotImplementedError("Login method not implemented")

    def register(self, request: RegisterRequest):
        self.user_repository.create_user(request=request)

        jwt_token = generate_access_token(user_id=request.email)

        response: RegisterResponse = RegisterResponse(
            access_token=jwt_token,
            email=request.email,
            firstName=request.firstName,
            lastName=request.lastName,
            handle=request.handle,
            user_id=request.email
        )

        return response
