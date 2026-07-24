"""Repository dependency providers."""

from functools import lru_cache

from app.repository.log_repository import LogRepository
from app.repository.log_repository_protocol import LogRepositoryProtocol
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_rating_repository_protocol import MovieRatingRepositoryProtocol
from app.repository.movie_repository import MovieRepository
from app.repository.movie_repository_protocol import MovieRepositoryProtocol
from app.repository.notification_repository import NotificationRepository
from app.repository.notification_repository_protocol import NotificationRepositoryProtocol
from app.repository.stats_repository import StatsRepository
from app.repository.stats_repository_protocol import StatsRepositoryProtocol
from app.repository.user_repository import UserRepository
from app.repository.user_repository_protocol import UserRepositoryProtocol


@lru_cache
def get_movie_repository() -> MovieRepositoryProtocol:
    """Return the active movie repository implementation."""

    return MovieRepository()


@lru_cache
def get_user_repository() -> UserRepositoryProtocol:
    """Return the active user repository implementation."""

    return UserRepository()


@lru_cache
def get_movie_rating_repository() -> MovieRatingRepositoryProtocol:
    """Return the active movie-rating repository implementation."""

    return MovieRatingRepository()


@lru_cache
def get_log_repository() -> LogRepositoryProtocol:
    """Return the active log repository implementation."""

    return LogRepository()


@lru_cache
def get_notification_repository() -> NotificationRepositoryProtocol:
    """Return the PostgreSQL notification repository."""

    return NotificationRepository()


@lru_cache
def get_stats_repository() -> StatsRepositoryProtocol:
    """Return the PostgreSQL cross-table stats read repository."""

    return StatsRepository()
