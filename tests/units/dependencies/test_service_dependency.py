from app.dependencies.repository_dependency import (
    get_follow_repository,
    get_log_repository,
    get_stats_repository,
    get_user_repository,
)
from app.dependencies.service_dependency import (
    get_follow_service,
    get_log_service,
    get_notification_service,
    get_stats_service,
    get_user_service,
)
from app.repository.follow_repository import FollowRepository
from app.repository.log_repository import LogRepository
from app.repository.stats_repository import StatsRepository
from app.services.log_list_cache_service import LogListCacheService


def clear_caches() -> None:
    get_follow_repository.cache_clear()
    get_log_repository.cache_clear()
    get_stats_repository.cache_clear()
    get_user_repository.cache_clear()
    get_follow_service.cache_clear()
    get_log_service.cache_clear()
    get_notification_service.cache_clear()
    get_stats_service.cache_clear()
    get_user_service.cache_clear()


def test_get_log_service_uses_postgres_repository_and_response_cache():
    clear_caches()

    service = get_log_service()

    assert isinstance(service.log_repository, LogRepository)
    assert isinstance(service.log_list_cache_service, LogListCacheService)

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
    assert follow_service.notification_service is get_notification_service()

    clear_caches()


def test_provider_factory_supplies_all_movie_consumers(monkeypatch):
    from app.dependencies import provider_dependency
    from app.dependencies.service_dependency import (
        clear_movie_related_service_dependencies,
        get_movie_rating_service,
        get_movie_service,
    )
    from tests.fakes.movie_provider import FakeMovieProvider

    fake = FakeMovieProvider()
    monkeypatch.setattr(provider_dependency, "get_movie_provider", lambda: fake)
    clear_movie_related_service_dependencies()
    try:
        movie_service = get_movie_service()
        assert movie_service.provider is fake
        log_service = get_log_service()
        rating_service = get_movie_rating_service()
        assert log_service.movie_service is movie_service
        assert rating_service.movie_service is movie_service
        clear_movie_related_service_dependencies()
        new_movie_service = get_movie_service()
        assert new_movie_service is not movie_service
        assert get_log_service() is not log_service
        assert get_movie_rating_service() is not rating_service
        assert get_log_service().movie_service is new_movie_service
        assert get_movie_rating_service().movie_service is new_movie_service
    finally:
        clear_movie_related_service_dependencies()
