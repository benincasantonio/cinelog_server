from beanie import PydanticObjectId

from app.repository.log_repository import LogRepository
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_repository import MovieRepository
from app.repository.user_repository import UserRepository
from app.services.movie_service import MovieService
from app.schemas.movie_schemas import MovieResponse
from app.schemas.log_schemas import (
    LogCreateRequest,
    LogCreateResponse,
    LogUpdateRequest,
    LogListRequest,
    LogListResponse,
    LogListItem,
)
from app.services.stats_cache_service import StatsCacheService
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes
from app.models.movie import Movie


class LogService:
    """Service layer for log operations."""

    def __init__(
        self,
        log_repository: LogRepository,
        movie_service: MovieService | None = None,
        movie_repository: MovieRepository | None = None,
        movie_rating_repository: MovieRatingRepository | None = None,
        stats_cache_service: StatsCacheService | None = None,
        user_repository: UserRepository | None = None,
    ):
        self.log_repository = log_repository
        # Initialize movie service if not provided
        if movie_service is None:
            movie_repository = MovieRepository()
            movie_service = MovieService(movie_repository)

        self.movie_service = movie_service
        self.movie_rating_repository = (
            movie_rating_repository or MovieRatingRepository()
        )
        self.movie_repository = movie_repository or MovieRepository()
        self.stats_cache_service = stats_cache_service or StatsCacheService()
        self.user_repository = user_repository or UserRepository()

    def _map_movie_to_response(self, movie: Movie) -> MovieResponse:
        return MovieResponse(
            id=movie.id,
            title=movie.title,
            tmdb_id=movie.tmdb_id,
            poster_path=movie.poster_path,
            release_date=movie.release_date,
            overview=movie.overview,
            vote_average=movie.vote_average,
            runtime=movie.runtime,
            original_language=movie.original_language,
            created_at=movie.created_at,
            updated_at=movie.updated_at,
        )

    async def create_log(
        self, user_id: PydanticObjectId, request: LogCreateRequest
    ) -> LogCreateResponse:
        """
        Create a new viewing log entry.

        If the movie doesn't exist in our database, it will be fetched from TMDB
        and created automatically.
        """
        # Ensure movie exists (find or create from TMDB)
        movie: Movie = await self.movie_service.find_or_create_movie(
            tmdb_id=request.tmdb_id
        )

        # Update the movieId in the request with the actual database ID
        request.movie_id = str(movie.id)

        # Auto-populate posterPath from movie if not provided
        if not request.poster_path and movie.poster_path:
            request.poster_path = movie.poster_path

        log = await self.log_repository.create_log(
            user_id=user_id, create_log_request=request
        )

        await self.stats_cache_service.invalidate_user_stats(user_id)

        return LogCreateResponse(
            id=str(log.id),
            movie_id=str(log.movie_id),
            movie=self._map_movie_to_response(movie),
            tmdb_id=log.tmdb_id,
            date_watched=log.date_watched,
            viewing_notes=log.viewing_notes,
            poster_path=log.poster_path,
            watched_where=log.watched_where,
        )

    async def update_log(
        self, user_id: PydanticObjectId, log_id: str, request: LogUpdateRequest
    ) -> LogCreateResponse:
        """
        Update an existing log entry.
        """
        log = await self.log_repository.update_log(
            log_id=log_id, user_id=user_id, update_request=request
        )

        if not log:
            # Log not found or doesn't belong to user
            raise AppException(ErrorCodes.LOG_NOT_FOUND)

        movie = await self.movie_service.get_movie_by_id(log.movie_id)
        if movie is None:
            raise AppException(ErrorCodes.MOVIE_NOT_FOUND)

        await self.stats_cache_service.invalidate_user_stats(user_id)

        return LogCreateResponse(
            id=str(log.id),
            movie_id=str(log.movie_id),
            movie=self._map_movie_to_response(movie),
            tmdb_id=log.tmdb_id,
            date_watched=log.date_watched,
            viewing_notes=log.viewing_notes,
            poster_path=log.poster_path,
            watched_where=log.watched_where,
        )

    async def get_user_logs(
        self, user_id: PydanticObjectId, request: LogListRequest
    ) -> LogListResponse:
        """
        Get list of user's viewing logs with optional filtering and sorting.
        """

        logs_data = await self.log_repository.find_logs_by_user_id(
            user_id=user_id,
            watched_where=request.watched_where,
            date_watched_from=request.date_watched_from or None,
            date_watched_to=request.date_watched_to or None,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
        )

        unique_movie_ids = {log_data.movie_id for log_data in logs_data}

        movie_ratings = (
            await self.movie_rating_repository.find_movie_ratings_by_user_and_movie_ids(
                user_id=user_id, movie_ids=unique_movie_ids
            )
        )

        movies = await self.movie_repository.find_movies_by_ids(unique_movie_ids)

        movie_map = {movie.id: movie for movie in movies}
        rating_map = {rating.movie_id: rating.rating for rating in movie_ratings}

        log_items = []
        for log_data in logs_data:
            movie = movie_map.get(log_data.movie_id)
            movie_response = self._map_movie_to_response(movie) if movie else None

            movie_rating = rating_map.get(log_data.movie_id)

            log_items.append(
                LogListItem(
                    id=log_data.id,
                    movie_id=log_data.movie_id,
                    movie=movie_response,
                    movie_rating=movie_rating,
                    tmdb_id=log_data.tmdb_id,
                    date_watched=log_data.date_watched,
                    viewing_notes=log_data.viewing_notes,
                    poster_path=log_data.poster_path,
                    watched_where=log_data.watched_where,
                )
            )
        return LogListResponse(logs=log_items)

    async def get_user_logs_by_handle(
        self,
        handle: str,
        requester_id: PydanticObjectId,
        request: LogListRequest,
    ) -> LogListResponse:
        user = await self.user_repository.find_user_by_handle(handle.strip())
        if not user:
            raise AppException(ErrorCodes.USER_NOT_FOUND)

        is_owner = str(user.id) == str(requester_id)
        if not is_owner and user.profile_visibility != "public":
            raise AppException(ErrorCodes.PROFILE_NOT_PUBLIC)

        return await self.get_user_logs(user_id=user.id, request=request)
