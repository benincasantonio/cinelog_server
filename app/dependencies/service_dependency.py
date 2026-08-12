"""Service dependencies for FastAPI ``Depends(...)``.

Each ``get_*_service`` is wrapped with ``@lru_cache`` so it returns the
same process-wide instance. Endpoints declare ``Depends(get_*_service)``.
Tests can swap a whole service through
``app.dependency_overrides[get_*_service] = ...``.
"""

from functools import lru_cache

from app.dependencies.repository_dependency import (
    get_follow_repository,
    get_log_repository,
    get_movie_rating_repository,
    get_movie_repository,
    get_notification_repository,
    get_stats_repository,
    get_user_repository,
)
from app.repository.log_cache_repository import LogCacheRepository
from app.services.auth_rate_limit_service import AuthRateLimitService
from app.services.auth_service import AuthService
from app.services.follow_service import FollowService
from app.services.log_service import LogService
from app.services.movie_rating_service import MovieRatingService
from app.services.movie_service import MovieService
from app.services.notification_service import NotificationService
from app.services.stats_service import StatsService
from app.services.user_service import UserService


def _get_runtime_log_repository():
    return LogCacheRepository(get_log_repository())


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService(get_user_repository())


@lru_cache
def get_auth_rate_limit_service() -> AuthRateLimitService:
    return AuthRateLimitService()


@lru_cache
def get_user_service() -> UserService:
    return UserService(
        user_repository=get_user_repository(),
        follow_repository=get_follow_repository(),
    )


@lru_cache
def get_follow_service() -> FollowService:
    return FollowService(
        user_repository=get_user_repository(),
        follow_repository=get_follow_repository(),
        notification_service=get_notification_service(),
    )


@lru_cache
def get_movie_service() -> MovieService:
    return MovieService(get_movie_repository())


@lru_cache
def get_movie_rating_service() -> MovieRatingService:
    return MovieRatingService(
        movie_rating_repository=get_movie_rating_repository(),
        movie_service=get_movie_service(),
    )


@lru_cache
def get_log_service() -> LogService:
    return LogService(
        log_repository=_get_runtime_log_repository(),
        movie_service=get_movie_service(),
        movie_repository=get_movie_repository(),
        movie_rating_repository=get_movie_rating_repository(),
        user_repository=get_user_repository(),
    )


@lru_cache
def get_notification_service() -> NotificationService:
    return NotificationService(repository=get_notification_repository())


@lru_cache
def get_stats_service() -> StatsService:
    return StatsService(
        stats_repository=get_stats_repository(),
    )
