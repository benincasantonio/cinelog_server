from app.dependencies.repository_dependency import get_log_repository
from app.dependencies.service_dependency import _get_runtime_log_repository
from app.repository.log_cache_repository import LogCacheRepository
from app.repository.log_repository import LogRepository
from app.repository.postgres_log_repository import PostgresLogRepository


def clear_caches() -> None:
    get_log_repository.cache_clear()


def test_get_runtime_log_repository_uses_cache_wrapper_for_mongo(monkeypatch):
    clear_caches()
    monkeypatch.delenv("DB_BACKEND", raising=False)

    repository = _get_runtime_log_repository()

    assert isinstance(repository, LogCacheRepository)
    assert isinstance(repository.repository, LogRepository)

    clear_caches()


def test_get_runtime_log_repository_skips_cache_wrapper_for_postgres(monkeypatch):
    clear_caches()
    monkeypatch.setenv("DB_BACKEND", "postgres")

    repository = _get_runtime_log_repository()

    assert isinstance(repository, PostgresLogRepository)
    assert not isinstance(repository, LogCacheRepository)

    clear_caches()
