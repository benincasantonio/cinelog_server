import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import date

from app.services.user_service import UserService
from app.schemas.log_schemas import LogListRequest, LogListResponse
from app.schemas.user_schemas import UpdateProfileRequest
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes


@pytest.fixture
def mock_user_repository():
    return AsyncMock()


@pytest.fixture
def user_service(mock_user_repository):
    return UserService(user_repository=mock_user_repository)


def create_mock_user(
    user_id="user123",
    first_name="John",
    last_name="Doe",
    email="john@example.com",
    handle="johndoe",
    bio=None,
    date_of_birth=None,
    password_hash="$2b$12$hashed_password",
    profile_visibility="public",
):
    """Helper to create a mock user with proper attributes."""
    mock_user = Mock()
    mock_user.id = user_id
    mock_user.first_name = first_name
    mock_user.last_name = last_name
    mock_user.email = email
    mock_user.handle = handle
    mock_user.bio = bio
    mock_user.date_of_birth = date_of_birth or date(1990, 1, 1)
    mock_user.password_hash = password_hash
    mock_user.profile_visibility = profile_visibility
    return mock_user


class TestUserService:
    """Tests for UserService."""

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, user_service, mock_user_repository):
        """Test successful user info retrieval."""
        mock_user = create_mock_user()
        mock_user_repository.find_user_by_id.return_value = mock_user

        result = await user_service.get_user_info("user123")

        assert result.id == "user123"
        assert result.first_name == "John"
        assert result.last_name == "Doe"
        mock_user_repository.find_user_by_id.assert_awaited_once_with("user123")

    @pytest.mark.asyncio
    async def test_get_user_info_user_not_found(
        self, user_service, mock_user_repository
    ):
        """Test get_user_info when user is not found."""
        mock_user_repository.find_user_by_id.return_value = None

        with pytest.raises(AppException) as exc_info:
            await user_service.get_user_info("nonexistent_user")

        assert exc_info.value.error.error_code == ErrorCodes.USER_NOT_FOUND.error_code


class TestUpdateProfile:
    """Tests for UserService.update_profile."""

    @pytest.mark.asyncio
    async def test_update_profile_success(self, user_service, mock_user_repository):
        """Test successful profile update."""
        updated_user = create_mock_user(first_name="Jane", bio="New bio")
        mock_user_repository.update_user_profile.return_value = updated_user

        request = UpdateProfileRequest(first_name="Jane", bio="New bio")
        result = await user_service.update_profile("user123", request)

        assert result.first_name == "Jane"
        assert result.bio == "New bio"
        mock_user_repository.update_user_profile.assert_awaited_once_with(
            "user123", {"first_name": "Jane", "bio": "New bio"}
        )

    @pytest.mark.asyncio
    async def test_update_profile_partial_fields(
        self, user_service, mock_user_repository
    ):
        """Test that only provided fields are sent to the repository."""
        updated_user = create_mock_user(last_name="Smith")
        mock_user_repository.update_user_profile.return_value = updated_user

        request = UpdateProfileRequest(last_name="Smith")
        await user_service.update_profile("user123", request)

        mock_user_repository.update_user_profile.assert_awaited_once_with(
            "user123", {"last_name": "Smith"}
        )

    @pytest.mark.asyncio
    async def test_update_profile_user_not_found(
        self, user_service, mock_user_repository
    ):
        """Test update_profile when user does not exist."""
        mock_user_repository.update_user_profile.return_value = None

        request = UpdateProfileRequest(first_name="Jane")
        with pytest.raises(AppException) as exc_info:
            await user_service.update_profile("nonexistent", request)

        assert exc_info.value.error.error_code == ErrorCodes.USER_NOT_FOUND.error_code

    @pytest.mark.asyncio
    async def test_update_profile_empty_request_raises(
        self, user_service, mock_user_repository
    ):
        """Test that an empty update request raises USER_NOT_FOUND."""
        request = UpdateProfileRequest()
        with pytest.raises(AppException) as exc_info:
            await user_service.update_profile("user123", request)

        assert exc_info.value.error.error_code == ErrorCodes.USER_NOT_FOUND.error_code
        mock_user_repository.update_user_profile.assert_not_awaited()


class TestChangePassword:
    """Tests for UserService.change_password."""

    @pytest.mark.asyncio
    async def test_change_password_success(self, user_service, mock_user_repository):
        """Test successful password change."""
        mock_user = create_mock_user(password_hash="$2b$12$hashed")
        mock_user_repository.find_user_by_id.return_value = mock_user
        mock_user_repository.update_password.return_value = mock_user

        with (
            patch(
                "app.services.user_service.PasswordService.verify_password",
                side_effect=[
                    True,
                    False,
                ],  # current matches, new does not match current
            ),
            patch(
                "app.services.user_service.PasswordService.get_password_hash",
                return_value="$2b$12$new_hashed",
            ),
        ):
            result = await user_service.change_password(
                "user123", "current_pass", "new_pass"
            )

        assert result.message == "Password changed successfully"
        mock_user_repository.update_password.assert_awaited_once_with(
            mock_user, "$2b$12$new_hashed"
        )

    @pytest.mark.asyncio
    async def test_change_password_user_not_found(
        self, user_service, mock_user_repository
    ):
        """Test change_password when user does not exist."""
        mock_user_repository.find_user_by_id.return_value = None

        with pytest.raises(AppException) as exc_info:
            await user_service.change_password("nonexistent", "current", "new")

        assert exc_info.value.error.error_code == ErrorCodes.USER_NOT_FOUND.error_code

    @pytest.mark.asyncio
    async def test_change_password_no_password_hash(
        self, user_service, mock_user_repository
    ):
        """Test change_password when user has no password hash (legacy user)."""
        mock_user = create_mock_user(password_hash=None)
        mock_user_repository.find_user_by_id.return_value = mock_user

        with pytest.raises(AppException) as exc_info:
            await user_service.change_password("user123", "current", "new")

        assert exc_info.value.error.error_code == ErrorCodes.USER_NOT_FOUND.error_code

    @pytest.mark.asyncio
    async def test_change_password_wrong_current_password(
        self, user_service, mock_user_repository
    ):
        """Test change_password with incorrect current password."""
        mock_user = create_mock_user(password_hash="$2b$12$hashed")
        mock_user_repository.find_user_by_id.return_value = mock_user

        with patch(
            "app.services.user_service.PasswordService.verify_password",
            return_value=False,
        ):
            with pytest.raises(AppException) as exc_info:
                await user_service.change_password("user123", "wrong", "new_pass")

        assert (
            exc_info.value.error.error_code
            == ErrorCodes.INVALID_CURRENT_PASSWORD.error_code
        )

    @pytest.mark.asyncio
    async def test_change_password_same_as_current(
        self, user_service, mock_user_repository
    ):
        """Test change_password when new password matches current."""
        mock_user = create_mock_user(password_hash="$2b$12$hashed")
        mock_user_repository.find_user_by_id.return_value = mock_user

        with patch(
            "app.services.user_service.PasswordService.verify_password",
            return_value=True,  # both current and new match
        ):
            with pytest.raises(AppException) as exc_info:
                await user_service.change_password("user123", "same_pass", "same_pass")

        assert exc_info.value.error.error_code == ErrorCodes.SAME_PASSWORD.error_code


class TestGetPublicProfile:
    """Tests for UserService.get_public_profile."""

    @pytest.fixture
    def mock_user_repository(self):
        return AsyncMock()

    @pytest.fixture
    def user_service(self, mock_user_repository):
        return UserService(user_repository=mock_user_repository)

    @pytest.mark.asyncio
    async def test_get_public_profile_public_visibility(
        self, user_service, mock_user_repository
    ):
        """Test that a public profile is returned for any authenticated user."""
        mock_user = create_mock_user(profile_visibility="public")
        mock_user.id = "other_user"
        mock_user_repository.find_user_by_handle.return_value = mock_user

        result = await user_service.get_public_profile("johndoe", "requesting_user")

        assert result.handle == "johndoe"
        assert result.profile_visibility == "public"

    @pytest.mark.asyncio
    async def test_get_public_profile_private_visibility(
        self, user_service, mock_user_repository
    ):
        """Test that a private profile still returns basic info."""
        mock_user = create_mock_user(profile_visibility="private")
        mock_user.id = "other_user"
        mock_user_repository.find_user_by_handle.return_value = mock_user

        result = await user_service.get_public_profile("johndoe", "requesting_user")

        assert result.handle == "johndoe"
        assert result.profile_visibility == "private"

    @pytest.mark.asyncio
    async def test_get_public_profile_own_profile(
        self, user_service, mock_user_repository
    ):
        """Test that own profile is always accessible."""
        mock_user = create_mock_user(profile_visibility="private")
        mock_user.id = "user123"
        mock_user_repository.find_user_by_handle.return_value = mock_user

        result = await user_service.get_public_profile("johndoe", "user123")

        assert result.handle == "johndoe"

    @pytest.mark.asyncio
    async def test_get_public_profile_user_not_found(
        self, user_service, mock_user_repository
    ):
        """Test that USER_NOT_FOUND is raised when handle does not exist."""
        mock_user_repository.find_user_by_handle.return_value = None

        with pytest.raises(AppException) as exc_info:
            await user_service.get_public_profile("nonexistent", "user123")

        assert exc_info.value.error.error_code == ErrorCodes.USER_NOT_FOUND.error_code


class TestGetPublicUserLogs:
    """Tests for UserService.get_public_user_logs."""

    @pytest.fixture
    def mock_user_repository(self):
        return AsyncMock()

    @pytest.fixture
    def mock_log_repository(self):
        return AsyncMock()

    @pytest.fixture
    def user_service(self, mock_user_repository, mock_log_repository):
        return UserService(
            user_repository=mock_user_repository,
            log_repository=mock_log_repository,
        )

    @pytest.mark.asyncio
    async def test_get_public_user_logs_own_profile(
        self, user_service, mock_user_repository, mock_log_repository
    ):
        """Test that own profile logs are always accessible."""
        mock_user = create_mock_user(profile_visibility="private")
        mock_user.id = "user123"
        mock_user_repository.find_user_by_handle.return_value = mock_user

        with patch(
            "app.services.log_service.LogService.get_user_logs",
            new_callable=AsyncMock,
            return_value=LogListResponse(logs=[]),
        ):
            result = await user_service.get_public_user_logs(
                "johndoe", "user123", LogListRequest()
            )

        assert result.logs == []

    @pytest.mark.asyncio
    async def test_get_public_user_logs_public_profile(
        self, user_service, mock_user_repository, mock_log_repository
    ):
        """Test that public profile logs are accessible."""
        mock_user = create_mock_user(profile_visibility="public")
        mock_user.id = "other_user"
        mock_user_repository.find_user_by_handle.return_value = mock_user

        with patch(
            "app.services.log_service.LogService.get_user_logs",
            new_callable=AsyncMock,
            return_value=LogListResponse(logs=[]),
        ):
            result = await user_service.get_public_user_logs(
                "johndoe", "requesting_user", LogListRequest()
            )

        assert result.logs == []

    @pytest.mark.asyncio
    async def test_get_public_user_logs_private_profile_raises(
        self, user_service, mock_user_repository
    ):
        """Test that private profile raises PROFILE_NOT_PUBLIC."""
        mock_user = create_mock_user(profile_visibility="private")
        mock_user.id = "other_user"
        mock_user_repository.find_user_by_handle.return_value = mock_user

        with pytest.raises(AppException) as exc_info:
            await user_service.get_public_user_logs(
                "johndoe", "requesting_user", LogListRequest()
            )

        assert (
            exc_info.value.error.error_code == ErrorCodes.PROFILE_NOT_PUBLIC.error_code
        )

    @pytest.mark.asyncio
    async def test_get_public_user_logs_friends_only_raises(
        self, user_service, mock_user_repository
    ):
        """Test that friends_only profile raises PROFILE_NOT_PUBLIC (stubbed as private)."""
        mock_user = create_mock_user(profile_visibility="friends_only")
        mock_user.id = "other_user"
        mock_user_repository.find_user_by_handle.return_value = mock_user

        with pytest.raises(AppException) as exc_info:
            await user_service.get_public_user_logs(
                "johndoe", "requesting_user", LogListRequest()
            )

        assert (
            exc_info.value.error.error_code == ErrorCodes.PROFILE_NOT_PUBLIC.error_code
        )

    @pytest.mark.asyncio
    async def test_get_public_user_logs_user_not_found(
        self, user_service, mock_user_repository
    ):
        """Test that USER_NOT_FOUND is raised when handle does not exist."""
        mock_user_repository.find_user_by_handle.return_value = None

        with pytest.raises(AppException) as exc_info:
            await user_service.get_public_user_logs(
                "nonexistent", "user123", LogListRequest()
            )

        assert exc_info.value.error.error_code == ErrorCodes.USER_NOT_FOUND.error_code
