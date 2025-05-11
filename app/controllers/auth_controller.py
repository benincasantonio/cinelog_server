from flask import Blueprint, request, jsonify

from app.repository.user_repository import UserRepository
from app.schemas.user_schemas import UserCreateRequest
from app.services.auth_service import AuthService

auth_controller = Blueprint("auth", __name__)

user_repository = UserRepository()
auth_service = AuthService(user_repository)

@auth_controller.post("/login")
def login():
    """
    Handle user login.
    """
    raise NotImplementedError("Login method not implemented")

@auth_controller.post("/register")
def register():
    """
    Handle user registration.
    """
    request_data = request.get_json()

    user_create_request: UserCreateRequest = UserCreateRequest(
        firstName=request_data["firstName"],
        lastName=request_data["lastName"],
        email=request_data["email"],
        handle=request_data["handle"],
        password=request_data["password"],
        dateOfBirth=request_data["dateOfBirth"]
    )

    response = auth_service.register(request=user_create_request)
    
    return response.model_dump_json(), 201
