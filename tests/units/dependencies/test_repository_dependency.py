import pytest

from app.dependencies.repository_dependency import (
    get_log_repository,
    get_movie_rating_repository,
    get_movie_repository,
    get_user_repository,
)
from app.repository.log_repository import LogRepository
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_repository import MovieRepository
from app.repository.postgres_log_repository import PostgresLogRepository
from app.repository.postgres_movie_rating_repository import PostgresMovieRatingRepository
from app.repository.postgres_movie_repository import PostgresMovieRepository
from app.repository.postgres_user_repository import PostgresUserRepository
from app.repository.user_repository import UserRepository


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


def test_get_movie_repository_defaults_to_mongo(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)

    repository = get_movie_repository()

    assert isinstance(repository, MovieRepository)


def test_get_movie_repository_returns_postgres_when_backend_is_postgres(monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "postgres")

    repository = get_movie_repository()

    assert isinstance(repository, PostgresMovieRepository)


def test_get_log_repository_defaults_to_mongo(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)

    repository = get_log_repository()

    assert isinstance(repository, LogRepository)


def test_get_log_repository_returns_postgres_when_backend_is_postgres(monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "postgres")

    repository = get_log_repository()

    assert isinstance(repository, PostgresLogRepository)


def test_get_movie_rating_repository_defaults_to_mongo(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)

    repository = get_movie_rating_repository()

    assert isinstance(repository, MovieRatingRepository)


def test_get_movie_rating_repository_returns_postgres_when_backend_is_postgres(monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "postgres")

    repository = get_movie_rating_repository()

    assert isinstance(repository, PostgresMovieRatingRepository)


def test_get_user_repository_defaults_to_mongo(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)

    repository = get_user_repository()

    assert isinstance(repository, UserRepository)


def test_get_user_repository_returns_postgres_when_backend_is_postgres(monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "postgres")

    repository = get_user_repository()

    assert isinstance(repository, PostgresUserRepository)
