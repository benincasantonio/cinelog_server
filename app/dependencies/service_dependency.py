"""Service dependencies for FastAPI ``Depends(...)``.

Each ``get_*_service`` is wrapped with ``@lru_cache`` so it returns the
same process-wide instance. Endpoints declare ``Depends(get_*_service)``.
Tests can swap a whole service through
``app.dependency_overrides[get_*_service] = ...``.
"""

from functools import lru_cache

from app.dependencies.repository_dependency import (
    get_log_repository,
    get_movie_rating_repository,
    get_movie_repository,
    get_notification_repository,
    get_notification_unit_of_work,
    get_outbound_message_repository,
    get_outbound_message_service,
    get_stats_repository,
    get_user_repository,
)
from app.repository.log_cache_repository import LogCacheRepository
from app.services.auth_rate_limit_service import AuthRateLimitService
from app.services.auth_service import AuthService
from app.services.log_service import LogService
from app.services.movie_rating_service import MovieRatingService
from app.services.movie_service import MovieService
from app.services.notification_service import NotificationService
from app.services.outbound_message_delivery_service import OutboundMessageDeliveryService
from app.services.stats_service import StatsService
from app.services.user_service import UserService


def _get_runtime_log_repository():
    return LogCacheRepository(get_log_repository())


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService(get_user_repository(), outbound_message_service=get_outbound_message_service())


@lru_cache
def get_auth_rate_limit_service() -> AuthRateLimitService:
    return AuthRateLimitService()


@lru_cache
def get_user_service() -> UserService:
    return UserService(user_repository=get_user_repository())


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
    return NotificationService(
        repository=get_notification_repository(),
        unit_of_work=get_notification_unit_of_work(),
    )


@lru_cache
def get_stats_service() -> StatsService:
    return StatsService(
        stats_repository=get_stats_repository(),
    )


@lru_cache
def get_outbound_message_delivery_service() -> OutboundMessageDeliveryService:
    """Return the cached delivery-cycle service (used by tests/tooling, not the worker).

    The worker process constructs its own instance directly instead of using this
    provider, because importing this module transitively imports ``NotificationService``,
    whose import chain requires ``CURSOR_PAGINATION_HMAC_SECRET`` — an env var the
    worker has no reason to need.
    """

    return OutboundMessageDeliveryService(outbound_message_repository=get_outbound_message_repository())
