"""Password whitespace regressions through HTTP, real bcrypt, and PostgreSQL."""

from unittest.mock import patch

import pytest

from app.dependencies.repository_dependency import get_user_repository
from tests.e2e.conftest import register_and_login

PADDED_PASSWORDS = [" password123 ", "       a"]
PADDED_IDS = ["surrounding-spaces", "whitespace-padded"]


def _account_data(password: str) -> dict:
    return {
        "email": "password-whitespace@example.com",
        "password": password,
        "firstName": "Password",
        "lastName": "Whitespace",
        "handle": "passwordwhitespace",
        "dateOfBirth": "1990-01-01",
        "locale": "en-US",
    }


async def _login_status(async_client, email: str, password: str) -> int:
    response = await async_client.post("/v1/auth/login", json={"email": email, "password": password})
    return response.status_code


@pytest.mark.parametrize("password", PADDED_PASSWORDS, ids=PADDED_IDS)
async def test_register_keeps_password_whitespace(async_client, password):
    account_data = _account_data(password)

    await register_and_login(async_client, account_data)

    assert await _login_status(async_client, account_data["email"], password.strip()) == 401


@pytest.mark.parametrize("password", PADDED_PASSWORDS, ids=PADDED_IDS)
async def test_reset_password_keeps_password_whitespace(async_client, password):
    account_data = _account_data("original-password")
    await register_and_login(async_client, account_data)

    with patch("app.services.email_service.EmailService.send_reset_password_email"):
        response = await async_client.post("/v1/auth/forgot-password", json={"email": account_data["email"]})
    assert response.status_code == 200
    user = await get_user_repository().find_user_by_email(account_data["email"])

    response = await async_client.post(
        "/v1/auth/reset-password",
        json={"email": account_data["email"], "code": user.reset_password_code, "newPassword": password},
    )
    assert response.status_code == 200

    assert await _login_status(async_client, account_data["email"], password) == 200
    assert await _login_status(async_client, account_data["email"], password.strip()) == 401
