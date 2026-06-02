"""Repository dependency providers and backend selection."""

from functools import lru_cache

from app.db.postgres import is_postgres_required
from app.repository.log_repository import LogRepository
from app.repository.log_repository_protocol import LogRepositoryProtocol
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_rating_repository_protocol import MovieRatingRepositoryProtocol
from app.repository.movie_repository import MovieRepository
from app.repository.movie_repository_protocol import MovieRepositoryProtocol
from app.repository.postgres_log_repository import PostgresLogRepository
from app.repository.postgres_movie_rating_repository import PostgresMovieRatingRepository
from app.repository.postgres_movie_repository import PostgresMovieRepository
from app.repository.postgres_user_repository import PostgresUserRepository
from app.repository.user_repository import UserRepository
from app.repository.user_repository_protocol import UserRepositoryProtocol


class RepositoryActivationError(RuntimeError):
    """Raised when an unsafe repository activation is requested."""


@lru_cache
def get_movie_repository() -> MovieRepositoryProtocol:
    """Return the active movie repository implementation.

    ``DB_BACKEND=postgres`` selects ``PostgresMovieRepository`` during the
    migration window; otherwise the legacy Mongo implementation stays active.
    """

    if is_postgres_required():
        return PostgresMovieRepository()

    return MovieRepository()


@lru_cache
def get_user_repository() -> UserRepositoryProtocol:
    """Return the active user repository implementation.

    ``DB_BACKEND=postgres`` selects ``PostgresUserRepository`` during the
    migration window; otherwise the legacy Mongo implementation stays active.
    """

    if is_postgres_required():
        return PostgresUserRepository()

    return UserRepository()


@lru_cache
def get_movie_rating_repository() -> MovieRatingRepositoryProtocol:
    """Return the active movie-rating repository implementation.

    ``DB_BACKEND=postgres`` selects ``PostgresMovieRatingRepository`` during
    the migration window; otherwise the legacy Mongo implementation stays
    active.
    """

    if is_postgres_required():
        return PostgresMovieRatingRepository()

    return MovieRatingRepository()


@lru_cache
def get_log_repository() -> LogRepositoryProtocol:
    """Return the active log repository implementation.

    ``DB_BACKEND=postgres`` selects ``PostgresLogRepository`` during the
    migration window; otherwise the legacy Mongo implementation stays active.
    """

    if is_postgres_required():
        return PostgresLogRepository()

    return LogRepository()
