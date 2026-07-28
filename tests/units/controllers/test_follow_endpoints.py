"""Controller tests for idempotent follow mutations."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import app
from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_follow_service
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def override_auth():
    user_id = uuid4()
    return lambda: user_id


def _csrf_request_kwargs():
    return {
        "cookies": {
            "__Host-access_token": "token",
            "__Host-csrf_token": "csrf-token",
        },
        "headers": {"X-CSRF-Token": "csrf-token"},
    }


class TestFollowController:
    @patch.object(get_follow_service(), "follow_user", new_callable=AsyncMock)
    def test_follow_returns_204(self, mock_follow, client, override_auth):
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.put("/v1/users/TargetUser/follow", **_csrf_request_kwargs())

        app.dependency_overrides = {}
        assert response.status_code == 204
        assert response.content == b""
        mock_follow.assert_awaited_once_with(follower_id=override_auth(), handle="TargetUser")

    @patch.object(get_follow_service(), "unfollow_user", new_callable=AsyncMock)
    def test_unfollow_returns_204(self, mock_unfollow, client, override_auth):
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.delete("/v1/users/TargetUser/follow", **_csrf_request_kwargs())

        app.dependency_overrides = {}
        assert response.status_code == 204
        assert response.content == b""
        mock_unfollow.assert_awaited_once_with(follower_id=override_auth(), handle="TargetUser")

    @patch.object(get_follow_service(), "follow_user", new_callable=AsyncMock)
    def test_follow_returns_structured_self_follow_error(self, mock_follow, client, override_auth):
        app.dependency_overrides[auth_dependency] = override_auth
        mock_follow.side_effect = AppException(ErrorCodes.SELF_FOLLOW_NOT_ALLOWED)

        response = client.put("/v1/users/self/follow", **_csrf_request_kwargs())

        app.dependency_overrides = {}
        assert response.status_code == 400
        assert response.json()["error_code_name"] == "SELF_FOLLOW_NOT_ALLOWED"

    @patch.object(get_follow_service(), "follow_user", new_callable=AsyncMock)
    def test_follow_requires_csrf(self, mock_follow, client, override_auth):
        app.dependency_overrides[auth_dependency] = override_auth

        response = client.put(
            "/v1/users/target/follow",
            cookies={"__Host-access_token": "token"},
        )

        app.dependency_overrides = {}
        assert response.status_code == 403
        mock_follow.assert_not_awaited()

    def test_follow_requires_authentication(self, client):
        app.dependency_overrides = {}

        response = client.put(
            "/v1/users/target/follow",
            cookies={"__Host-csrf_token": "csrf-token"},
            headers={"X-CSRF-Token": "csrf-token"},
        )

        assert response.status_code == 401
