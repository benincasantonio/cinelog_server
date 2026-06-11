"""Repository dependency providers."""

from functools import lru_cache

from app.repository.log_repository_protocol import LogRepositoryProtocol
from app.repository.movie_rating_repository_protocol import MovieRatingRepositoryProtocol
from app.repository.movie_repository_protocol import MovieRepositoryProtocol
from app.repository.postgres_log_repository import PostgresLogRepository
from app.repository.postgres_movie_rating_repository import PostgresMovieRatingRepository
from app.repository.postgres_movie_repository import PostgresMovieRepository
from app.repository.postgres_user_repository import PostgresUserRepository
from app.repository.user_repository_protocol import UserRepositoryProtocol


@lru_cache
def get_movie_repository() -> MovieRepositoryProtocol:
    """Return the active movie repository implementation."""

    return PostgresMovieRepository()


@lru_cache
def get_user_repository() -> UserRepositoryProtocol:
    """Return the active user repository implementation."""

    return PostgresUserRepository()


@lru_cache
def get_movie_rating_repository() -> MovieRatingRepositoryProtocol:
    """Return the active movie-rating repository implementation."""

    return PostgresMovieRatingRepository()


@lru_cache
def get_log_repository() -> LogRepositoryProtocol:
    """Return the active log repository implementation."""

    return PostgresLogRepository()
