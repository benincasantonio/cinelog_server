import pytest

from app.dependencies.repository_dependency import (
    get_follow_repository,
    get_log_repository,
    get_movie_rating_repository,
    get_movie_repository,
    get_stats_repository,
    get_user_repository,
)
from app.repository.follow_repository import FollowRepository
from app.repository.log_repository import LogRepository
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_repository import MovieRepository
from app.repository.stats_repository import StatsRepository
from app.repository.user_repository import UserRepository


@pytest.fixture(autouse=True)
def clear_repository_caches():
    get_follow_repository.cache_clear()
    get_log_repository.cache_clear()
    get_movie_rating_repository.cache_clear()
    get_movie_repository.cache_clear()
    get_stats_repository.cache_clear()
    get_user_repository.cache_clear()
    yield
    get_follow_repository.cache_clear()
    get_log_repository.cache_clear()
    get_movie_rating_repository.cache_clear()
    get_movie_repository.cache_clear()
    get_stats_repository.cache_clear()
    get_user_repository.cache_clear()


def test_get_follow_repository_returns_postgres_repository():
    repository = get_follow_repository()

    assert isinstance(repository, FollowRepository)
    assert get_follow_repository() is repository


def test_get_movie_repository_returns_postgres_repository():
    repository = get_movie_repository()

    assert isinstance(repository, MovieRepository)
    assert get_movie_repository() is repository


def test_get_log_repository_returns_postgres_repository():
    repository = get_log_repository()

    assert isinstance(repository, LogRepository)
    assert get_log_repository() is repository


def test_get_movie_rating_repository_returns_postgres_repository():
    repository = get_movie_rating_repository()

    assert isinstance(repository, MovieRatingRepository)
    assert get_movie_rating_repository() is repository


def test_get_user_repository_returns_postgres_repository():
    repository = get_user_repository()

    assert isinstance(repository, UserRepository)
    assert get_user_repository() is repository


def test_get_stats_repository_returns_postgres_repository():
    repository = get_stats_repository()

    assert isinstance(repository, StatsRepository)
    assert get_stats_repository() is repository
