from app.dependencies.repository_dependency import get_log_repository
from app.dependencies.service_dependency import _get_runtime_log_repository
from app.repository.log_cache_repository import LogCacheRepository
from app.repository.log_repository import LogRepository


def clear_caches() -> None:
    get_log_repository.cache_clear()


def test_get_runtime_log_repository_wraps_postgres_repository_with_cache():
    clear_caches()

    repository = _get_runtime_log_repository()

    assert isinstance(repository, LogCacheRepository)
    assert isinstance(repository.repository, LogRepository)

    clear_caches()
