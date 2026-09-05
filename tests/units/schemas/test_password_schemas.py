"""New-password byte limits must not restrict existing credentials."""

import pytest
from pydantic import ValidationError

from app.schemas.auth_schemas import LoginRequest, RegisterRequest, ResetPasswordRequest
from app.schemas.user_schemas import ChangePasswordRequest


@pytest.fixture(params=[RegisterRequest, ResetPasswordRequest, ChangePasswordRequest])
def password_schema(request):
    if request.param is RegisterRequest:
        return (
            request.param,
            "password",
            {
                "firstName": "Jane",
                "lastName": "Doe",
                "email": "jane@example.com",
                "handle": "janedoe",
                "dateOfBirth": "1990-01-01",
                "locale": "en-US",
                "verificationCode": "ABC123",
            },
        )
    if request.param is ResetPasswordRequest:
        return request.param, "newPassword", {"email": "jane@example.com", "code": "ABC123"}
    return request.param, "newPassword", {"currentPassword": "é" * 128}


@pytest.mark.parametrize("password", ["a" * 8, "a" * 72, "é" * 36, "🔐" * 18, " password "])
def test_accepts_valid_new_password_without_normalizing(password_schema, password):
    schema, field, data = password_schema

    result = schema.model_validate({**data, field: password})

    assert result.model_dump(by_alias=True)[field] == password


@pytest.mark.parametrize("password", ["a" * 7, "🔐" * 7, "a" * 73, "a" + "é" * 36, " " + "a" * 72])
def test_rejects_invalid_new_password(password_schema, password):
    schema, field, data = password_schema

    with pytest.raises(ValidationError) as exc_info:
        schema.model_validate({**data, field: password})

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == (field,)
    assert password not in errors[0]["msg"]
    if len(password) <= 72 and len(password.encode("utf-8")) > 72:
        assert "72 UTF-8 bytes" in errors[0]["msg"]


def test_new_password_openapi_limits(password_schema):
    schema, field, _ = password_schema
    property_schema = schema.model_json_schema()["properties"][field]

    assert property_schema["minLength"] == 8
    assert property_schema["maxLength"] == 72
    assert "72 UTF-8 bytes" in property_schema["description"]


def test_login_keeps_unbounded_password_input():
    password = "é" * 256

    assert LoginRequest(email="jane@example.com", password=password).password == password


def test_current_password_keeps_existing_character_limits():
    password = "é" * 128
    assert ChangePasswordRequest(currentPassword=password, newPassword="password123").current_password == password

    with pytest.raises(ValidationError):
        ChangePasswordRequest(currentPassword=password + "é", newPassword="password123")
