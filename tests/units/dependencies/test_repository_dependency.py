import pytest

from app.dependencies.repository_dependency import RepositoryActivationError, get_movie_repository
from app.repository.movie_repository import MovieRepository


@pytest.fixture(autouse=True)
def clear_movie_repository_cache():
    get_movie_repository.cache_clear()
    yield
    get_movie_repository.cache_clear()


def test_get_movie_repository_defaults_to_mongo(monkeypatch):
    monkeypatch.delenv("DB_BACKEND", raising=False)

    repository = get_movie_repository()

    assert isinstance(repository, MovieRepository)


def test_get_movie_repository_raises_for_unsafe_postgres_activation(monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "postgres")

    with pytest.raises(RepositoryActivationError, match="not yet safe"):
        get_movie_repository()
