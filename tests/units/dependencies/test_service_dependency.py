from app.dependencies.repository_dependency import (
    get_follow_repository,
    get_log_repository,
    get_stats_repository,
    get_user_repository,
)
from app.dependencies.service_dependency import (
    _get_runtime_log_repository,
    get_follow_service,
    get_stats_service,
    get_user_service,
)
from app.repository.follow_repository import FollowRepository
from app.repository.log_cache_repository import LogCacheRepository
from app.repository.log_repository import LogRepository
from app.repository.stats_repository import StatsRepository


def clear_caches() -> None:
    get_follow_repository.cache_clear()
    get_log_repository.cache_clear()
    get_stats_repository.cache_clear()
    get_user_repository.cache_clear()
    get_follow_service.cache_clear()
    get_stats_service.cache_clear()
    get_user_service.cache_clear()


def test_get_runtime_log_repository_wraps_postgres_repository_with_cache():
    clear_caches()

    repository = _get_runtime_log_repository()

    assert isinstance(repository, LogCacheRepository)
    assert isinstance(repository.repository, LogRepository)

    clear_caches()


def test_get_stats_service_uses_dedicated_stats_repository():
    clear_caches()

    service = get_stats_service()

    assert isinstance(service.stats_repository, StatsRepository)

    clear_caches()


def test_follow_and_user_services_share_follow_repository():
    clear_caches()

    follow_service = get_follow_service()
    user_service = get_user_service()

    assert isinstance(follow_service.follow_repository, FollowRepository)
    assert user_service.follow_repository is follow_service.follow_repository

    clear_caches()
