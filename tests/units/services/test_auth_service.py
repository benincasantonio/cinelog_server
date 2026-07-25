from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.config.registration_verification_config import REGISTRATION_VERIFICATION_TTL_SECONDS
from app.schemas.auth_schemas import RegisterRequest
from app.services.auth_rate_limit_service import AuthRateLimitService
from app.services.auth_service import AuthService
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


class TestAuthService:
    @pytest.fixture
    def mock_user_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_outbound_message_service(self):
        return AsyncMock()

    @pytest.fixture
    def mock_registration_verification_service(self):
        return AsyncMock()

    @pytest.fixture
    def auth_service(self, mock_user_repo, mock_outbound_message_service, mock_registration_verification_service):
        return AuthService(
            user_repository=mock_user_repo,
            outbound_message_service=mock_outbound_message_service,
            registration_verification_service=mock_registration_verification_service,
        )

    @pytest.mark.asyncio
    async def test_send_registration_verification_code_for_new_email(
        self,
        auth_service,
        mock_user_repo,
        mock_outbound_message_service,
        mock_registration_verification_service,
    ):
        mock_user_repo.find_user_by_email.return_value = None
        mock_registration_verification_service.issue_code.return_value = "ABC123"

        await auth_service.send_registration_verification_code("User@Example.com ")

        mock_user_repo.find_user_by_email.assert_awaited_once_with("user@example.com")
        mock_registration_verification_service.issue_code.assert_awaited_once_with("user@example.com")
        mock_outbound_message_service.enqueue_registration_verification.assert_awaited_once()
        args, kwargs = mock_outbound_message_service.enqueue_registration_verification.call_args
        assert args == ("user@example.com", "ABC123")
        # The queued message has to die with the code itself, or a late retry
        # delivers a code Redis has already dropped.
        assert kwargs["expires_at"] > datetime.now(UTC)
        assert kwargs["expires_at"] <= datetime.now(UTC) + timedelta(seconds=REGISTRATION_VERIFICATION_TTL_SECONDS)
        mock_outbound_message_service.enqueue_registration_existing_account.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_registration_verification_code_for_existing_email(
        self,
        auth_service,
        mock_user_repo,
        mock_outbound_message_service,
        mock_registration_verification_service,
    ):
        mock_user_repo.find_user_by_email.return_value = SimpleNamespace(email="user@example.com")

        await auth_service.send_registration_verification_code("User@Example.com ")

        mock_user_repo.find_user_by_email.assert_awaited_once_with("user@example.com")
        mock_registration_verification_service.issue_code.assert_not_awaited()
        mock_outbound_message_service.enqueue_registration_existing_account.assert_awaited_once_with("user@example.com")
        mock_outbound_message_service.enqueue_registration_verification.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_forgot_password_hides_outbox_failures_to_stay_enumeration_safe(
        self, auth_service, mock_user_repo, mock_outbound_message_service
    ):
        """An unknown email returns success without any write.

        If a known account answered with a 500 when the outbox write failed, the
        difference between the two responses would reveal whether the account exists.
        """

        mock_user_repo.find_user_by_email.return_value = SimpleNamespace(email="known@example.com")
        mock_outbound_message_service.enqueue_password_reset.side_effect = RuntimeError("database went away")

        # Must not raise: the unknown-account branch returns None, so this one must too.
        assert await auth_service.forgot_password("known@example.com") is None

    @pytest.mark.asyncio
    async def test_forgot_password_success(self, auth_service, mock_user_repo, mock_outbound_message_service):
        email = "test@example.com"
        mock_user = SimpleNamespace(email=email)
        mock_user_repo.find_user_by_email.return_value = mock_user

        await auth_service.forgot_password(email)

        mock_user_repo.set_reset_password_code.assert_awaited_once()
        mock_outbound_message_service.enqueue_password_reset.assert_awaited_once()

        repo_call_args = mock_user_repo.set_reset_password_code.call_args[0]
        email_call_args = mock_outbound_message_service.enqueue_password_reset.call_args[0]

        reset_code_repo = repo_call_args[1]
        reset_code_email = email_call_args[1]

        assert reset_code_repo == reset_code_email

        stored_expiry = repo_call_args[2]
        queued_expiry = mock_outbound_message_service.enqueue_password_reset.call_args.kwargs["expires_at"]
        assert queued_expiry == stored_expiry

    @pytest.mark.asyncio
    async def test_register_success(self, auth_service, mock_user_repo, mock_registration_verification_service):
        request = RegisterRequest(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            password="password123",
            handle="johndoe",
            date_of_birth=date(1990, 1, 1),
            profile_visibility="private",
            bio=None,
            verification_code="ABC123",
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
            profile_visibility="private",
        )
        mock_user_repo.create_user.return_value = mock_created_user

        response = await auth_service.register(request)

        assert response.email == "john@example.com"
        mock_registration_verification_service.validate_code.assert_awaited_once_with("john@example.com", "ABC123")
        mock_user_repo.create_user.assert_awaited_once()
        mock_registration_verification_service.delete_code.assert_awaited_once_with("john@example.com")

        call_args = mock_user_repo.create_user.call_args[1]
        assert "password_hash" in call_args["request"].model_dump()
        assert call_args["request"].password_hash != "password123"

    @pytest.mark.asyncio
    async def test_register_rejects_invalid_verification_code(
        self,
        auth_service,
        mock_user_repo,
        mock_registration_verification_service,
    ):
        request = RegisterRequest(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            password="password123",
            handle="johndoe",
            date_of_birth=date(1990, 1, 1),
            profile_visibility="private",
            bio=None,
            verification_code="BAD999",
        )
        mock_registration_verification_service.validate_code.side_effect = AppException(
            ErrorCodes.INVALID_EMAIL_VERIFICATION_CODE
        )

        with pytest.raises(AppException) as exc_info:
            await auth_service.register(request)

        assert exc_info.value.error == ErrorCodes.INVALID_EMAIL_VERIFICATION_CODE
        mock_user_repo.find_user_by_email.assert_not_awaited()
        mock_user_repo.create_user.assert_not_awaited()
        mock_registration_verification_service.delete_code.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service, mock_user_repo):
        email = "john@example.com"
        password = "password123"
        hashed_pw = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"

        mock_user = SimpleNamespace(email=email, password_hash=hashed_pw)
        mock_user_repo.find_user_by_email.return_value = mock_user

        with pytest.MonkeyPatch.context() as m:
            from app.services.password_service import PasswordService

            m.setattr(PasswordService, "verify_password", lambda p, h: p == "password123")

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
        self,
        auth_service,
        mock_user_repo,
        mock_registration_verification_service,
    ):
        request = RegisterRequest(
            first_name="Jane",
            last_name="Doe",
            email="Jane.Doe@EXAMPLE.com",
            password="password123",
            handle="janedoe",
            date_of_birth=date(1995, 1, 1),
            profile_visibility="public",
            bio=None,
            verification_code="ABC123",
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
            profile_visibility="public",
        )
        mock_user_repo.create_user.return_value = mock_created_user

        response = await auth_service.register(request)

        assert response.email == "jane.doe@example.com"
        mock_registration_verification_service.validate_code.assert_awaited_once_with("jane.doe@example.com", "ABC123")
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

            m.setattr(PasswordService, "verify_password", lambda p, h: p == "password123")

            user = await auth_service.login(email_input, password)
            assert user == mock_user
            mock_user_repo.find_user_by_email.assert_awaited_with(email_stored)


class TestAuthRateLimitService:
    @pytest.fixture
    def rate_limit_service(self):
        return AuthRateLimitService()

    def test_build_account_key_hashes_normalized_email(self):
        key = AuthRateLimitService.build_account_key("User@Example.com ")

        assert key.startswith("identifier:")
        assert "User@Example.com" not in key
        assert "user@example.com" not in key

    def test_build_account_key_uses_dedicated_rate_limit_secret(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_HMAC_SECRET", "secret-one")
        with patch(
            "app.services.auth_rate_limit_service._RATE_LIMIT_HMAC_SECRET",
            "secret-one",
        ):
            first_key = AuthRateLimitService.build_account_key("user@example.com")

        monkeypatch.setenv("RATE_LIMIT_HMAC_SECRET", "secret-two")
        with patch(
            "app.services.auth_rate_limit_service._RATE_LIMIT_HMAC_SECRET",
            "secret-two",
        ):
            second_key = AuthRateLimitService.build_account_key("user@example.com")

        assert first_key != second_key

    def test_register_verification_account_limit_blocks_after_five_attempts(self, rate_limit_service):
        email = "User@Example.com "

        for _ in range(5):
            rate_limit_service.enforce_register_verification_limit(email)
            rate_limit_service.record_register_verification_attempt(email)

        with pytest.raises(AppException) as exc_info:
            rate_limit_service.enforce_register_verification_limit("user@example.com")

        assert exc_info.value.error == ErrorCodes.RATE_LIMIT_EXCEEDED
