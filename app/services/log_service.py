from app.repository.log_repository import LogRepository
from app.repository.movie_repository import MovieRepository
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
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes
from cinelog_server.app.models.movie import Movie


class LogService:
    """Service layer for log operations."""

    def __init__(
        self, log_repository: LogRepository, movie_service: MovieService = None
    ):
        self.log_repository = log_repository
        # Initialize movie service if not provided
        if movie_service is None:
            movie_repository = MovieRepository()
            self.movie_service = MovieService(movie_repository)
        else:
            self.movie_service = movie_service

    def _map_movie_to_response(self, movie) -> MovieResponse:
        if not movie:
            return None
        return MovieResponse(
            id=str(movie.id),
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

    def create_log(self, user_id: str, request: LogCreateRequest) -> LogCreateResponse:
        """
        Create a new viewing log entry.

        If the movie doesn't exist in our database, it will be fetched from TMDB
        and created automatically.
        """
        # Ensure movie exists (find or create from TMDB)
        movie: Movie = self.movie_service.find_or_create_movie(tmdb_id=request.tmdb_id)

        # Update the movieId in the request with the actual database ID
        request.movie_id = str(movie.id)

        # Auto-populate posterPath from movie if not provided
        if not request.poster_path and movie.poster_path:
            request.poster_path = movie.poster_path

        log = self.log_repository.create_log(
            user_id=user_id, create_log_request=request
        )

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

    def update_log(
        self, user_id: str, log_id: str, request: LogUpdateRequest
    ) -> LogCreateResponse:
        """
        Update an existing log entry.
        """
        log = self.log_repository.update_log(
            log_id=log_id, user_id=user_id, update_request=request
        )

        if not log:
            # Log not found or doesn't belong to user
            raise AppException(ErrorCodes.LOG_NOT_FOUND)

        movie: Movie = self.movie_service.get_movie_by_id(str(log.movie_id))

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

    def get_user_logs(self, user_id: str, request: LogListRequest) -> LogListResponse:
        """
        Get list of user's viewing logs with optional filtering and sorting.
        """
        logs_data = self.log_repository.find_logs_by_user_id(
            user_id=user_id, request=request
        )

        log_items = []
        for log_data in logs_data:
            movie = log_data.get("movie")
            log_items.append(
                LogListItem(
                    id=log_data["id"],
                    movie_id=str(log_data["movieId"]),
                    movie=self._map_movie_to_response(movie),
                    movie_rating=log_data.get("movieRating"),
                    tmdb_id=log_data["tmdbId"],
                    date_watched=log_data["dateWatched"],
                    viewing_notes=log_data.get("viewingNotes"),
                    poster_path=log_data.get("posterPath"),
                    watched_where=log_data.get("watchedWhere"),
                )
            )

        return LogListResponse(logs=log_items)
