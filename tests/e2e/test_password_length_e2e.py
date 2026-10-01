"""Password length regressions through HTTP, real bcrypt, and PostgreSQL."""

from unittest.mock import patch

import pytest

from app.dependencies.repository_dependency import get_user_repository
from app.utils.error_codes_utils import ErrorCodes
from tests.e2e.conftest import register_and_login


@pytest.fixture
def account_data():
    return {
        "email": "password-length@example.com",
        "password": "original-password",
        "firstName": "Password",
        "lastName": "Test",
        "handle": "passwordlength",
        "dateOfBirth": "1990-01-01",
        "locale": "en-US",
    }


@pytest.mark.parametrize("password", ["a" * 73, "a" + "é" * 36], ids=["ascii", "utf8"])
async def test_register_rejects_long_password_without_consuming_code(async_client, account_data, password):
    with patch("app.services.email_service.EmailService.send_registration_verification_email") as send_email:
        response = await async_client.post("/v1/auth/register/send-code", json={"email": account_data["email"]})
    assert response.status_code == 200
    code = send_email.call_args.args[1]
    payload = {**account_data, "password": password, "verificationCode": code}

    response = await async_client.post("/v1/auth/register", json=payload)

    assert response.status_code == 422
    assert password not in response.text
    assert code not in response.text
    assert all("input" not in error for error in response.json()["detail"])
    assert response.json()["detail"][0]["loc"] == ["body", "password"]
    assert await get_user_repository().find_user_by_email(account_data["email"]) is None

    # The same code remains usable; 36 two-byte characters are exactly 72 bytes.
    response = await async_client.post("/v1/auth/register", json={**payload, "password": "é" * 36})
    assert response.status_code == 201
    response = await async_client.post("/v1/auth/login", json={"email": account_data["email"], "password": "é" * 36})
    assert response.status_code == 200


@pytest.mark.parametrize("operation", ["reset", "change"])
@pytest.mark.parametrize("password", ["a" * 73, "a" + "é" * 36], ids=["ascii", "utf8"])
async def test_rejected_new_password_preserves_credentials(async_client, account_data, operation, password):
    login = await register_and_login(async_client, account_data)
    headers = {"X-CSRF-Token": login["csrfToken"]}
    repository = get_user_repository()
    user = await repository.find_user_by_email(account_data["email"])
    original_hash = user.password_hash

    if operation == "reset":
        with patch("app.services.email_service.EmailService.send_reset_password_email"):
            response = await async_client.post("/v1/auth/forgot-password", json={"email": account_data["email"]})
        assert response.status_code == 200
        user = await repository.find_user_by_email(account_data["email"])
        payload = {"email": account_data["email"], "code": user.reset_password_code, "newPassword": password}
        method, path = "POST", "/v1/auth/reset-password"
    else:
        payload = {"currentPassword": account_data["password"], "newPassword": password}
        method, path = "PUT", "/v1/users/settings/password"

    response = await async_client.request(method, path, json=payload, headers=headers)

    assert response.status_code == 422
    assert password not in response.text
    assert account_data["password"] not in response.text
    assert all("input" not in error for error in response.json()["detail"])
    assert response.json()["detail"][0]["loc"] == ["body", "newPassword"]
    stored_user = await repository.find_user_by_email(account_data["email"])
    assert stored_user.password_hash == original_hash
    if operation == "reset":
        assert payload["code"] not in response.text
        assert stored_user.reset_password_code == payload["code"]
        assert stored_user.reset_password_expires == user.reset_password_expires

    response = await async_client.request(method, path, json={**payload, "newPassword": "é" * 36}, headers=headers)
    assert response.status_code == 200
    if operation == "reset":
        stored_user = await repository.find_user_by_email(account_data["email"])
        assert stored_user.reset_password_code is None
    response = await async_client.post(
        "/v1/auth/login", json={"email": account_data["email"], "password": account_data["password"]}
    )
    assert response.status_code == 401
    response = await async_client.post("/v1/auth/login", json={"email": account_data["email"], "password": "é" * 36})
    assert response.status_code == 200


@pytest.mark.parametrize("password", ["a" * 72, "é" * 36, "🔐" * 18], ids=["ascii", "utf8", "emoji"])
async def test_oversized_credentials_are_rejected_without_changing_password(async_client, account_data, password):
    account_data["password"] = password
    login = await register_and_login(async_client, account_data)
    headers = {"X-CSRF-Token": login["csrfToken"]}
    repository = get_user_repository()
    user = await repository.find_user_by_email(account_data["email"])
    original_hash = user.password_hash
    oversized_password = password + "suffix"

    response = await async_client.post(
        "/v1/auth/login", json={"email": account_data["email"], "password": oversized_password}
    )
    assert response.status_code == 401
    assert response.json()["error_code_name"] == ErrorCodes.INVALID_CREDENTIALS.error_code_name

    response = await async_client.put(
        "/v1/users/settings/password",
        json={"currentPassword": oversized_password, "newPassword": "replacement-password"},
        headers=headers,
    )
    assert response.status_code == ErrorCodes.INVALID_CURRENT_PASSWORD.error_code
    assert response.json()["error_code_name"] == ErrorCodes.INVALID_CURRENT_PASSWORD.error_code_name

    response = await async_client.put(
        "/v1/users/settings/password",
        json={"currentPassword": password, "newPassword": password},
        headers=headers,
    )
    assert response.status_code == ErrorCodes.SAME_PASSWORD.error_code
    assert response.json()["error_code_name"] == ErrorCodes.SAME_PASSWORD.error_code_name
    stored_user = await repository.find_user_by_email(account_data["email"])
    assert stored_user.password_hash == original_hash

    response = await async_client.post("/v1/auth/login", json={"email": account_data["email"], "password": password})
    assert response.status_code == 200
    headers = {"X-CSRF-Token": response.json()["csrfToken"]}
    response = await async_client.put(
        "/v1/users/settings/password",
        json={"currentPassword": password, "newPassword": "replacement-password"},
        headers=headers,
    )
    assert response.status_code == 200
    response = await async_client.post(
        "/v1/auth/login", json={"email": account_data["email"], "password": "replacement-password"}
    )
    assert response.status_code == 200
    response = await async_client.post("/v1/auth/login", json={"email": account_data["email"], "password": password})
    assert response.status_code == 401
