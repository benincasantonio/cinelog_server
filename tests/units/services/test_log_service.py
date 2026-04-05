import pytest
from unittest.mock import AsyncMock, Mock
from datetime import date

from beanie import PydanticObjectId

from app.services.log_service import LogService
from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest, LogListRequest
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes


@pytest.fixture
def mock_log_repository():
    return AsyncMock()


@pytest.fixture
def mock_movie_service():
    return AsyncMock()


@pytest.fixture
def mock_stats_cache_service():
    return AsyncMock()


@pytest.fixture
def mock_user_repository():
    return AsyncMock()


@pytest.fixture
def log_service(
    mock_log_repository,
    mock_movie_service,
    mock_stats_cache_service,
    mock_user_repository,
):
    return LogService(
        log_repository=mock_log_repository,
        movie_service=mock_movie_service,
        stats_cache_service=mock_stats_cache_service,
        user_repository=mock_user_repository,
    )


class TestLogService:
    """Tests for LogService."""

    @pytest.mark.asyncio
    async def test_create_log_success(
        self, log_service, mock_log_repository, mock_movie_service
    ):
        """Test successful log creation."""
        # Setup mocks
        mock_movie = Mock()
        mock_movie.id = PydanticObjectId()
        mock_movie.title = "Test Movie"
        mock_movie.tmdb_id = 550
        mock_movie.poster_path = "/poster.jpg"
        mock_movie.release_date = date(2020, 1, 1)
        mock_movie.overview = "A description"
        mock_movie.vote_average = 8.5
        mock_movie.runtime = 120
        mock_movie.original_language = "en"
        mock_movie.created_at = date(2020, 1, 1)
        mock_movie.updated_at = date(2020, 1, 1)

        mock_movie_service.find_or_create_movie.return_value = mock_movie

        mock_log = Mock()
        mock_log.id = "log123"
        mock_log.movie_id = "movie123"
        mock_log.tmdb_id = 550
        mock_log.date_watched = date(2024, 1, 15)
        mock_log.viewing_notes = "Great movie!"
        mock_log.poster_path = "/poster.jpg"
        mock_log.watched_where = "cinema"

        mock_log_repository.create_log.return_value = mock_log

        # Execute
        request = LogCreateRequest(
            tmdb_id=550,
            date_watched=date(2024, 1, 15),
            viewing_notes="Great movie!",
            watched_where="cinema",
        )
        result = await log_service.create_log("user123", request)

        # Verify
        assert result.id == "log123"
        assert result.movie_id == "movie123"
        assert result.movie.title == "Test Movie"
        mock_movie_service.find_or_create_movie.assert_awaited_once_with(tmdb_id=550)
        mock_log_repository.create_log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_log_invalidates_stats_cache(
        self,
        log_service,
        mock_log_repository,
        mock_movie_service,
        mock_stats_cache_service,
    ):
        """Test that creating a log invalidates the stats cache."""
        user_id = PydanticObjectId()
        mock_movie = Mock()
        mock_movie.id = PydanticObjectId()
        mock_movie.title = "Test Movie"
        mock_movie.tmdb_id = 550
        mock_movie.poster_path = "/poster.jpg"
        mock_movie.release_date = None
        mock_movie.overview = None
        mock_movie.vote_average = None
        mock_movie.runtime = None
        mock_movie.original_language = "en"
        mock_movie.created_at = None
        mock_movie.updated_at = None
        mock_movie_service.find_or_create_movie.return_value = mock_movie

        mock_log = Mock()
        mock_log.id = "log123"
        mock_log.movie_id = "movie123"
        mock_log.tmdb_id = 550
        mock_log.date_watched = date(2024, 1, 15)
        mock_log.viewing_notes = None
        mock_log.poster_path = "/poster.jpg"
        mock_log.watched_where = "cinema"
        mock_log_repository.create_log.return_value = mock_log

        request = LogCreateRequest(
            tmdb_id=550, date_watched=date(2024, 1, 15), watched_where="cinema"
        )
        await log_service.create_log(user_id, request)

        mock_stats_cache_service.invalidate_user_stats.assert_awaited_once_with(user_id)

    @pytest.mark.asyncio
    async def test_create_log_auto_populate_poster(
        self, log_service, mock_log_repository, mock_movie_service
    ):
        """Test that posterPath is auto-populated from movie if not provided."""
        mock_movie = Mock()
        mock_movie.id = PydanticObjectId()
        mock_movie.title = "Test Movie"
        mock_movie.tmdb_id = 550
        mock_movie.poster_path = "/movie_poster.jpg"
        mock_movie.release_date = None
        mock_movie.overview = None
        mock_movie.vote_average = None
        mock_movie.runtime = None
        mock_movie.original_language = "en"
        mock_movie.created_at = None
        mock_movie.updated_at = None

        mock_movie_service.find_or_create_movie.return_value = mock_movie

        mock_log = Mock()
        mock_log.id = "log123"
        mock_log.movie_id = "movie123"
        mock_log.tmdb_id = 550
        mock_log.date_watched = date(2024, 1, 15)
        mock_log.viewing_notes = None
        mock_log.poster_path = "/movie_poster.jpg"
        mock_log.watched_where = "streaming"

        mock_log_repository.create_log.return_value = mock_log

        request = LogCreateRequest(
            tmdb_id=550,
            date_watched=date(2024, 1, 15),
            watched_where="streaming",
            # posterPath not provided
        )
        result = await log_service.create_log("user123", request)

        # Verify posterPath was populated from movie
        assert result.poster_path == "/movie_poster.jpg"

    @pytest.mark.asyncio
    async def test_update_log_success(
        self, log_service, mock_log_repository, mock_movie_service
    ):
        """Test successful log update."""
        mock_log = Mock()
        mock_log.id = "log123"
        mock_log.movie_id = "movie123"
        mock_log.tmdb_id = 550
        mock_log.date_watched = date(2024, 1, 15)
        mock_log.viewing_notes = "Updated notes"
        mock_log.poster_path = "/poster.jpg"
        mock_log.watched_where = "streaming"

        mock_log_repository.update_log.return_value = mock_log

        mock_movie = Mock()
        mock_movie.id = PydanticObjectId()
        mock_movie.title = "Test Movie"
        mock_movie.tmdb_id = 550
        mock_movie.poster_path = "/poster.jpg"
        mock_movie.release_date = None
        mock_movie.overview = None
        mock_movie.vote_average = None
        mock_movie.runtime = None
        mock_movie.original_language = "en"
        mock_movie.created_at = None
        mock_movie.updated_at = None

        mock_movie_service.get_movie_by_id.return_value = mock_movie

        request = LogUpdateRequest(viewing_notes="Updated notes")
        result = await log_service.update_log("user123", "log123", request)

        assert result.viewing_notes == "Updated notes"
        mock_log_repository.update_log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_log_invalidates_stats_cache(
        self,
        log_service,
        mock_log_repository,
        mock_movie_service,
        mock_stats_cache_service,
    ):
        """Test that updating a log invalidates the stats cache."""
        user_id = PydanticObjectId()
        mock_log = Mock()
        mock_log.id = "log123"
        mock_log.movie_id = "movie123"
        mock_log.tmdb_id = 550
        mock_log.date_watched = date(2024, 1, 15)
        mock_log.viewing_notes = "Updated notes"
        mock_log.poster_path = "/poster.jpg"
        mock_log.watched_where = "streaming"
        mock_log_repository.update_log.return_value = mock_log

        mock_movie = Mock()
        mock_movie.id = PydanticObjectId()
        mock_movie.title = "Test Movie"
        mock_movie.tmdb_id = 550
        mock_movie.poster_path = "/poster.jpg"
        mock_movie.release_date = None
        mock_movie.overview = None
        mock_movie.vote_average = None
        mock_movie.runtime = None
        mock_movie.original_language = "en"
        mock_movie.created_at = None
        mock_movie.updated_at = None
        mock_movie_service.get_movie_by_id.return_value = mock_movie

        request = LogUpdateRequest(viewing_notes="Updated notes")
        await log_service.update_log(user_id, "log123", request)

        mock_stats_cache_service.invalidate_user_stats.assert_awaited_once_with(user_id)

    @pytest.mark.asyncio
    async def test_update_log_not_found(self, log_service, mock_log_repository):
        """Test update log when log is not found."""
        mock_log_repository.update_log.return_value = None

        request = LogUpdateRequest(viewing_notes="Updated notes")

        with pytest.raises(AppException):
            await log_service.update_log("user123", "nonexistent_log", request)

    @pytest.mark.asyncio
    async def test_get_user_logs(
        self, log_service, mock_log_repository, mock_movie_service
    ):
        """Test getting user logs."""
        mock_movie = Mock()
        mock_movie.id = PydanticObjectId()
        mock_movie.title = "Test Movie"
        mock_movie.tmdb_id = 550
        mock_movie.poster_path = "/poster.jpg"
        mock_movie.release_date = None
        mock_movie.overview = None
        mock_movie.vote_average = None
        mock_movie.runtime = None
        mock_movie.original_language = "en"
        mock_movie.created_at = None
        mock_movie.updated_at = None

        mock_log = Mock()
        mock_log.id = PydanticObjectId()
        mock_log.movie_id = PydanticObjectId()
        mock_log.tmdb_id = 550
        mock_log.date_watched = date(2024, 1, 15)
        mock_log.viewing_notes = "Great!"
        mock_log.poster_path = "/poster.jpg"
        mock_log.watched_where = "cinema"

        # Ensure the movie.id matches log.movie_id
        mock_movie.id = mock_log.movie_id

        mock_log_repository.find_logs_by_user_id.return_value = [mock_log]

        mock_movie_repository = Mock()
        mock_movie_repository.find_movies_by_ids = AsyncMock(return_value=[mock_movie])

        mock_rating = Mock()
        mock_rating.rating = 8
        mock_rating.movie_id = mock_log.movie_id  # Match the log's movie_id
        mock_movie_rating_repository = Mock()
        mock_movie_rating_repository.find_movie_ratings_by_user_and_movie_ids = (
            AsyncMock(return_value=[mock_rating])
        )

        log_service.movie_repository = mock_movie_repository
        log_service.movie_rating_repository = mock_movie_rating_repository

        request = LogListRequest(sort_by="dateWatched", sort_order="desc")
        result = await log_service.get_user_logs(PydanticObjectId(), request)

        assert len(result.logs) == 1
        assert result.logs[0].movie_rating == 8


class TestGetUserLogsByHandle:
    def _create_mock_user(
        self,
        user_id="user456",
        handle="johndoe",
        profile_visibility="public",
    ):
        mock_user = Mock()
        mock_user.id = user_id
        mock_user.handle = handle
        mock_user.profile_visibility = profile_visibility
        return mock_user

    @pytest.mark.asyncio
    async def test_public_profile_allows_access(
        self, log_service, mock_user_repository
    ):
        mock_user = self._create_mock_user(
            user_id="user456", handle="johndoe", profile_visibility="public"
        )
        mock_user_repository.find_user_by_handle.return_value = mock_user

        mock_log = Mock()
        mock_log.id = PydanticObjectId()
        mock_log.movie_id = PydanticObjectId()
        mock_log.tmdb_id = 550
        mock_log.date_watched = date(2024, 1, 15)
        mock_log.viewing_notes = "Great!"
        mock_log.poster_path = "/poster.jpg"
        mock_log.watched_where = "cinema"

        log_service.log_repository.find_logs_by_user_id = AsyncMock(
            return_value=[mock_log]
        )
        log_service.movie_repository.find_movies_by_ids = AsyncMock(return_value=[])
        log_service.movie_rating_repository.find_movie_ratings_by_user_and_movie_ids = (
            AsyncMock(return_value=[])
        )

        request = LogListRequest()
        result = await log_service.get_user_logs_by_handle(
            handle="johndoe", requester_id="other_user", request=request
        )

        assert len(result.logs) == 1
        mock_user_repository.find_user_by_handle.assert_awaited_once_with("johndoe")

    @pytest.mark.asyncio
    async def test_own_profile_allows_access(self, log_service, mock_user_repository):
        mock_user = self._create_mock_user(
            user_id="user123", handle="johndoe", profile_visibility="private"
        )
        mock_user_repository.find_user_by_handle.return_value = mock_user

        log_service.log_repository.find_logs_by_user_id = AsyncMock(return_value=[])
        log_service.movie_repository.find_movies_by_ids = AsyncMock(return_value=[])
        log_service.movie_rating_repository.find_movie_ratings_by_user_and_movie_ids = (
            AsyncMock(return_value=[])
        )

        request = LogListRequest()
        result = await log_service.get_user_logs_by_handle(
            handle="johndoe", requester_id="user123", request=request
        )

        assert result.logs == []

    @pytest.mark.asyncio
    async def test_private_profile_blocks_access(
        self, log_service, mock_user_repository
    ):
        mock_user = self._create_mock_user(
            user_id="user456", handle="johndoe", profile_visibility="private"
        )
        mock_user_repository.find_user_by_handle.return_value = mock_user

        request = LogListRequest()
        with pytest.raises(AppException) as exc_info:
            await log_service.get_user_logs_by_handle(
                handle="johndoe", requester_id="other_user", request=request
            )

        assert (
            exc_info.value.error.error_code == ErrorCodes.PROFILE_NOT_PUBLIC.error_code
        )

    @pytest.mark.asyncio
    async def test_friends_only_profile_blocks_access(
        self, log_service, mock_user_repository
    ):
        mock_user = self._create_mock_user(
            user_id="user456", handle="johndoe", profile_visibility="friends_only"
        )
        mock_user_repository.find_user_by_handle.return_value = mock_user

        request = LogListRequest()
        with pytest.raises(AppException) as exc_info:
            await log_service.get_user_logs_by_handle(
                handle="johndoe", requester_id="other_user", request=request
            )

        assert (
            exc_info.value.error.error_code == ErrorCodes.PROFILE_NOT_PUBLIC.error_code
        )

    @pytest.mark.asyncio
    async def test_user_not_found(self, log_service, mock_user_repository):
        mock_user_repository.find_user_by_handle.return_value = None

        request = LogListRequest()
        with pytest.raises(AppException) as exc_info:
            await log_service.get_user_logs_by_handle(
                handle="nonexistent", requester_id="user123", request=request
            )

        assert exc_info.value.error.error_code == ErrorCodes.USER_NOT_FOUND.error_code
