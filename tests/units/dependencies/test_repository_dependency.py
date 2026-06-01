import pytest

from app.dependencies.repository_dependency import (
    RepositoryActivationError,
    get_movie_rating_repository,
    get_movie_repository,
    get_user_repository,
)
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_repository import MovieRepository
from app.repository.user_repository import UserRepository


@pytest.fixture(autouse=True)
def clear_repository_caches():
    get_movie_rating_repository.cache_clear()
    get_movie_repository.cache_clear()
    get_user_repository.cache_clear()
    yield
    get_movie_rating_repository.cache_clear()
    get_movie_repository.cache_clear()
    get_user_repository.cache_clear()


def test_get_movie_repository_defaults_to_mongo(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)

    repository = get_movie_repository()

    assert isinstance(repository, MovieRepository)


def test_get_movie_repository_raises_for_unsafe_postgres_activation(monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "postgres")

    with pytest.raises(RepositoryActivationError, match="not yet safe"):
        get_movie_repository()


def test_get_movie_rating_repository_defaults_to_mongo(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)

    repository = get_movie_rating_repository()

    assert isinstance(repository, MovieRatingRepository)


def test_get_movie_rating_repository_raises_for_unsafe_postgres_activation(monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "postgres")

    with pytest.raises(RepositoryActivationError, match="not yet safe"):
        get_movie_rating_repository()


def test_get_user_repository_defaults_to_mongo(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)

    repository = get_user_repository()

    assert isinstance(repository, UserRepository)


def test_get_user_repository_raises_for_unsafe_postgres_activation(monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "postgres")

    with pytest.raises(RepositoryActivationError, match="not yet safe"):
        get_user_repository()
