from app.dependencies.repository_dependency import get_log_repository, get_stats_repository
from app.dependencies.service_dependency import _get_runtime_log_repository, get_stats_service
from app.repository.log_cache_repository import LogCacheRepository
from app.repository.log_repository import LogRepository
from app.repository.stats_repository import StatsRepository


def clear_caches() -> None:
    get_log_repository.cache_clear()
    get_stats_repository.cache_clear()
    get_stats_service.cache_clear()


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
