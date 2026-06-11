import pytest

from app.dependencies.repository_dependency import (
    get_log_repository,
    get_movie_rating_repository,
    get_movie_repository,
    get_user_repository,
)
from app.repository.postgres_log_repository import PostgresLogRepository
from app.repository.postgres_movie_rating_repository import PostgresMovieRatingRepository
from app.repository.postgres_movie_repository import PostgresMovieRepository
from app.repository.postgres_user_repository import PostgresUserRepository


@pytest.fixture(autouse=True)
def clear_repository_caches():
    get_log_repository.cache_clear()
    get_movie_rating_repository.cache_clear()
    get_movie_repository.cache_clear()
    get_user_repository.cache_clear()
    yield
    get_log_repository.cache_clear()
    get_movie_rating_repository.cache_clear()
    get_movie_repository.cache_clear()
    get_user_repository.cache_clear()


def test_get_movie_repository_returns_postgres_repository():
    repository = get_movie_repository()

    assert isinstance(repository, PostgresMovieRepository)
    assert get_movie_repository() is repository


def test_get_log_repository_returns_postgres_repository():
    repository = get_log_repository()

    assert isinstance(repository, PostgresLogRepository)
    assert get_log_repository() is repository


def test_get_movie_rating_repository_returns_postgres_repository():
    repository = get_movie_rating_repository()

    assert isinstance(repository, PostgresMovieRatingRepository)
    assert get_movie_rating_repository() is repository


def test_get_user_repository_returns_postgres_repository():
    repository = get_user_repository()

    assert isinstance(repository, PostgresUserRepository)
    assert get_user_repository() is repository
