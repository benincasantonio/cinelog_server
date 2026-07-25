"""Repository dependency providers.

Also hosts the outbound-message enqueue service and the notification unit-of-work
provider (``get_outbound_message_service()``, ``get_notification_unit_of_work()``),
even though those are service-layer/orchestration objects rather than repositories.
``app/services/notification_service.py`` needs a unit-of-work provider and already
imports from this module; importing it from ``service_dependency.py`` instead would
create a cycle, because ``service_dependency.py`` imports ``NotificationService``.
"""

from functools import lru_cache

from app.repository.log_repository import LogRepository
from app.repository.log_repository_protocol import LogRepositoryProtocol
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_rating_repository_protocol import MovieRatingRepositoryProtocol
from app.repository.movie_repository import MovieRepository
from app.repository.movie_repository_protocol import MovieRepositoryProtocol
from app.repository.notification_repository import NotificationRepository
from app.repository.notification_repository_protocol import NotificationRepositoryProtocol
from app.repository.notification_unit_of_work import NotificationUnitOfWork
from app.repository.notification_unit_of_work_protocol import NotificationUnitOfWorkProtocol
from app.repository.outbound_message_repository import OutboundMessageRepository
from app.repository.outbound_message_repository_protocol import OutboundMessageRepositoryProtocol
from app.repository.stats_repository import StatsRepository
from app.repository.stats_repository_protocol import StatsRepositoryProtocol
from app.repository.user_repository import UserRepository
from app.repository.user_repository_protocol import UserRepositoryProtocol
from app.services.outbound_message_service import OutboundMessageService


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


@lru_cache
def get_outbound_message_repository() -> OutboundMessageRepositoryProtocol:
    """Return the PostgreSQL outbound-message (transactional outbox) repository."""

    return OutboundMessageRepository()


@lru_cache
def get_outbound_message_service() -> OutboundMessageService:
    """Return the cached outbound-message enqueue service (repository + renderers only).

    Lives here rather than ``service_dependency.py`` so ``get_notification_unit_of_work()``
    can share the exact same cached instance without importing ``service_dependency.py``
    (which imports ``NotificationService`` and would create a cycle).
    """

    return OutboundMessageService(
        outbound_message_repository=get_outbound_message_repository(),
        user_repository=get_user_repository(),
    )


@lru_cache
def get_notification_unit_of_work() -> NotificationUnitOfWorkProtocol:
    """Return the cached unit of work that creates a notification and its deliveries atomically."""

    return NotificationUnitOfWork(
        notification_repository=get_notification_repository(),
        outbound_message_service=get_outbound_message_service(),
    )
