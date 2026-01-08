from mongoengine import disconnect, connect
import mongomock
from app.models.movie import Movie
import pytest

from app.repository.movie_repository import MovieRepository
from app.schemas.movie_schemas import MovieCreateRequest, MovieUpdateRequest


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    # Disconnect from any existing connections first
    disconnect()
    # Connect to a test database using mongomock
    connect('mongoenginetest', host='localhost', mongo_client_class=mongomock.MongoClient)
    yield
    # Disconnect from the test database
    disconnect()

@pytest.fixture(autouse=True)
def clear_database():
    Movie.objects.delete()

@pytest.fixture
def movie_create_request() -> MovieCreateRequest:
    return MovieCreateRequest(
        title='Inception',
        tmdbId=111111
    )

@pytest.fixture
def movie_update_request() -> MovieUpdateRequest:
    return MovieUpdateRequest(
        title='Inception Updated',
    )

def test_movie_creation(movie_create_request: MovieCreateRequest):
    # Test movie creation
    repository = MovieRepository()
    movie = repository.create_movie(movie_create_request)

    # Assertions
    assert movie is not None
    assert movie.id is not None
    assert movie.title == movie_create_request.title
    assert movie.tmdbId == movie_create_request.tmdbId
    assert Movie.objects.count() == 1


def test_movie_update(movie_create_request: MovieCreateRequest, movie_update_request: MovieUpdateRequest):
    # Test movie update
    repository = MovieRepository()
    movie = repository.create_movie(movie_create_request)

    repository.update_movie(movie.id, movie_update_request)

    updated_movie = repository.find_movie_by_id(movie.id)

    # Assertions
    assert updated_movie is not None
    assert updated_movie.id == movie.id
    assert updated_movie.title == movie_update_request.title

def test_find_movie_by_id(movie_create_request: MovieCreateRequest):
    # Test finding a movie by ID
    repository = MovieRepository()
    movie = repository.create_movie(movie_create_request)

    found_movie = repository.find_movie_by_id(movie.id)

    # Assertions
    assert found_movie is not None
    assert found_movie.id == movie.id
    assert found_movie.title == movie_create_request.title
    assert found_movie.tmdbId == movie_create_request.tmdbId


def test_find_movie_by_tmdb_id(movie_create_request: MovieCreateRequest):
    # Test finding a movie by TMDB ID
    repository = MovieRepository()
    movie = repository.create_movie(movie_create_request)

    found_movie = repository.find_movie_by_tmdb_id(movie.tmdbId)

    # Assertions
    assert found_movie is not None
    assert found_movie.id == movie.id
    assert found_movie.title == movie_create_request.title
    assert found_movie.tmdbId == movie_create_request.tmdbId

