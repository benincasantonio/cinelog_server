"""Dependency wiring tests for notification persistence and service layers."""

from app.dependencies.repository_dependency import get_notification_repository
from app.dependencies.service_dependency import get_notification_service
from app.repository.notification_repository import NotificationRepository
from app.services.notification_service import NotificationService


def test_notification_dependencies_are_cached_and_layered():
    get_notification_service.cache_clear()
    get_notification_repository.cache_clear()

    repository = get_notification_repository()
    service = get_notification_service()

    assert isinstance(repository, NotificationRepository)
    assert get_notification_repository() is repository
    assert isinstance(service, NotificationService)
    assert service.repository is repository
    assert get_notification_service() is service

    get_notification_service.cache_clear()
    get_notification_repository.cache_clear()
