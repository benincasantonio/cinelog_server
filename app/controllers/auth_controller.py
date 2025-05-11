from flask import Blueprint, request, jsonify

from app.repository.user_repository import UserRepository
from app.schemas.auth_schemas import LoginRequest
from app.schemas.user_schemas import UserCreateRequest
from app.services.auth_service import AuthService
from app.utils.exceptions import AppException

auth_controller = Blueprint("auth", __name__)

user_repository = UserRepository()
auth_service = AuthService(user_repository)

@auth_controller.post("/login")
def login():
    """
    Handle user login.
    """
    request_data = request.get_json()

    user_login_request: LoginRequest = LoginRequest(
        emailOrHandle=request_data["emailOrHandle"],
        password=request_data["password"]
    )

    try:
        response = auth_service.login(request=user_login_request)
        return response.model_dump_json(), 200
    except AppException as e:
        return jsonify(e.error.model_dump()), e.error.error_code

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

    try:
        response = auth_service.register(request=user_create_request)
        return response.model_dump_json(), 201
    except AppException as e:
        return jsonify(e.error.model_dump()), e.error.error_code
