from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.auth_schemas import RegisterRequest
from app.services.auth_service import AuthService
from app.utils.exceptions import AppException


class TestAuthService:
    @pytest.fixture
    def mock_user_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_email_service(self):
        return MagicMock()

    @pytest.fixture
    def auth_service(self, mock_user_repo, mock_email_service):
        return AuthService(
            user_repository=mock_user_repo, email_service=mock_email_service
        )

    @pytest.mark.asyncio
    async def test_forgot_password_success(
        self, auth_service, mock_user_repo, mock_email_service
    ):
        email = "test@example.com"
        mock_user = SimpleNamespace(email=email)
        mock_user_repo.find_user_by_email.return_value = mock_user

        await auth_service.forgot_password(email)

        mock_user_repo.set_reset_password_code.assert_awaited_once()
        mock_email_service.send_reset_password_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_success(self, auth_service, mock_user_repo):
        request = RegisterRequest(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            password="password123",
            handle="johndoe",
            date_of_birth=date(1990, 1, 1),
        )

        mock_user_repo.find_user_by_email.return_value = None
        mock_user_repo.find_user_by_handle.return_value = None

        mock_created_user = SimpleNamespace(
            id="507f1f77bcf86cd799439011",
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            handle="johndoe",
            bio=None,
        )
        mock_user_repo.create_user.return_value = mock_created_user

        response = await auth_service.register(request)

        assert response.email == "john@example.com"
        mock_user_repo.create_user.assert_awaited_once()

        call_args = mock_user_repo.create_user.call_args[1]
        assert "password_hash" in call_args["request"].model_dump()
        assert call_args["request"].password_hash != "password123"

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service, mock_user_repo):
        email = "john@example.com"
        password = "password123"
        hashed_pw = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"

        mock_user = SimpleNamespace(email=email, password_hash=hashed_pw)
        mock_user_repo.find_user_by_email.return_value = mock_user

        with pytest.MonkeyPatch.context() as m:
            from app.services.password_service import PasswordService

            m.setattr(
                PasswordService, "verify_password", lambda p, h: p == "password123"
            )

            user = await auth_service.login(email, password)
            assert user == mock_user

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, auth_service, mock_user_repo):
        email = "john@example.com"
        hashed_pw = "hashed_secret"

        mock_user = SimpleNamespace(email=email, password_hash=hashed_pw)
        mock_user_repo.find_user_by_email.return_value = mock_user

        with pytest.MonkeyPatch.context() as m:
            from app.services.password_service import PasswordService

            m.setattr(PasswordService, "verify_password", lambda p, h: False)

            with pytest.raises(AppException) as exc:
                await auth_service.login(email, "wrongpassword")

            assert exc.value.error.error_code == 401

    @pytest.mark.asyncio
    async def test_login_migration_required(self, auth_service, mock_user_repo):
        mock_user = SimpleNamespace(email="old@example.com", password_hash=None)
        mock_user_repo.find_user_by_email.return_value = mock_user

        with pytest.raises(AppException) as exc:
            await auth_service.login("old@example.com", "anypassword")

        assert exc.value.error.error_code == 401

    @pytest.mark.asyncio
    async def test_register_email_case_insensitivity(
        self, auth_service, mock_user_repo
    ):
        request = RegisterRequest(
            first_name="Jane",
            last_name="Doe",
            email="Jane.Doe@EXAMPLE.com",
            password="password123",
            handle="janedoe",
            date_of_birth=date(1995, 1, 1),
        )

        mock_user_repo.find_user_by_email.return_value = None
        mock_user_repo.find_user_by_handle.return_value = None

        mock_created_user = SimpleNamespace(
            id="507f1f77bcf86cd799439012",
            email="jane.doe@example.com",
            first_name="Jane",
            last_name="Doe",
            handle="janedoe",
            bio=None,
        )
        mock_user_repo.create_user.return_value = mock_created_user

        response = await auth_service.register(request)

        assert response.email == "jane.doe@example.com"
        mock_user_repo.find_user_by_email.assert_awaited_with("jane.doe@example.com")

        call_args = mock_user_repo.create_user.call_args[1]
        assert call_args["request"].email == "jane.doe@example.com"

    @pytest.mark.asyncio
    async def test_login_email_case_insensitivity(self, auth_service, mock_user_repo):
        email_input = "John@EXAMPLE.com"
        email_stored = "john@example.com"
        password = "password123"
        hashed_pw = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"

        mock_user = SimpleNamespace(email=email_stored, password_hash=hashed_pw)
        mock_user_repo.find_user_by_email.return_value = mock_user

        with pytest.MonkeyPatch.context() as m:
            from app.services.password_service import PasswordService

            m.setattr(
                PasswordService, "verify_password", lambda p, h: p == "password123"
            )

            user = await auth_service.login(email_input, password)
            assert user == mock_user
            mock_user_repo.find_user_by_email.assert_awaited_with(email_stored)
