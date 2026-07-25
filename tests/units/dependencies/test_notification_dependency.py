"""Dependency wiring tests for notification and outbound-message persistence/service layers."""

from app.dependencies.repository_dependency import (
    get_notification_repository,
    get_outbound_message_repository,
)
from app.dependencies.service_dependency import (
    get_notification_service,
    get_notification_unit_of_work,
    get_outbound_message_delivery_service,
    get_outbound_message_service,
)
from app.repository.notification_repository import NotificationRepository
from app.repository.notification_unit_of_work import NotificationUnitOfWork
from app.repository.outbound_message_repository import OutboundMessageRepository
from app.services.notification_service import NotificationService
from app.services.outbound_message_delivery_service import OutboundMessageDeliveryService
from app.services.outbound_message_service import OutboundMessageService

_PROVIDERS = (
    get_notification_service,
    get_notification_repository,
    get_notification_unit_of_work,
    get_outbound_message_repository,
    get_outbound_message_service,
    get_outbound_message_delivery_service,
)


def _clear_caches() -> None:
    for provider in _PROVIDERS:
        provider.cache_clear()


def test_notification_dependencies_are_cached_and_layered():
    _clear_caches()

    repository = get_notification_repository()
    service = get_notification_service()

    assert isinstance(repository, NotificationRepository)
    assert get_notification_repository() is repository
    assert isinstance(service, NotificationService)
    assert service.repository is repository
    assert get_notification_service() is service

    _clear_caches()


def test_outbound_message_repository_is_cached():
    _clear_caches()

    repository = get_outbound_message_repository()

    assert isinstance(repository, OutboundMessageRepository)
    assert get_outbound_message_repository() is repository

    _clear_caches()


def test_outbound_message_service_is_cached_and_shares_the_repository_instance():
    _clear_caches()

    repository = get_outbound_message_repository()
    service = get_outbound_message_service()

    assert isinstance(service, OutboundMessageService)
    assert service.outbound_message_repository is repository
    assert get_outbound_message_service() is service

    _clear_caches()


def test_notification_unit_of_work_is_cached_and_layered():
    _clear_caches()

    notification_repository = get_notification_repository()
    outbound_message_service = get_outbound_message_service()
    unit_of_work = get_notification_unit_of_work()

    assert isinstance(unit_of_work, NotificationUnitOfWork)
    assert unit_of_work.notification_repository is notification_repository
    assert unit_of_work.outbound_message_service is outbound_message_service
    assert get_notification_unit_of_work() is unit_of_work

    notification_service = get_notification_service()
    assert notification_service.unit_of_work is unit_of_work

    _clear_caches()


def test_outbound_message_delivery_service_is_cached_and_shares_the_repository_instance():
    _clear_caches()

    repository = get_outbound_message_repository()
    delivery_service = get_outbound_message_delivery_service()

    assert isinstance(delivery_service, OutboundMessageDeliveryService)
    assert delivery_service.outbound_message_repository is repository
    assert get_outbound_message_delivery_service() is delivery_service

    _clear_caches()
