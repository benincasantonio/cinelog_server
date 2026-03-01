import pytest

from app.repository.movie_repository import MovieRepository
from app.schemas.movie_schemas import MovieCreateRequest, MovieUpdateRequest


@pytest.fixture
def movie_create_request() -> MovieCreateRequest:
    return MovieCreateRequest(title="Inception", tmdb_id=111111)


@pytest.fixture
def movie_update_request() -> MovieUpdateRequest:
    return MovieUpdateRequest(title="Inception Updated")


@pytest.mark.asyncio
async def test_movie_creation(beanie_test_db, movie_create_request: MovieCreateRequest):
    repository = MovieRepository()
    movie = await repository.create_movie(movie_create_request)

    assert movie is not None
    assert movie.id is not None
    assert movie.title == movie_create_request.title
    assert movie.tmdb_id == movie_create_request.tmdb_id


@pytest.mark.asyncio
async def test_movie_update(
    beanie_test_db,
    movie_create_request: MovieCreateRequest,
    movie_update_request: MovieUpdateRequest,
):
    repository = MovieRepository()
    movie = await repository.create_movie(movie_create_request)

    await repository.update_movie(movie.id, movie_update_request)
    updated_movie = await repository.find_movie_by_id(movie.id)

    assert updated_movie is not None
    assert updated_movie.id == movie.id
    assert updated_movie.title == movie_update_request.title


@pytest.mark.asyncio
async def test_find_movie_by_id(
    beanie_test_db, movie_create_request: MovieCreateRequest
):
    repository = MovieRepository()
    movie = await repository.create_movie(movie_create_request)

    found_movie = await repository.find_movie_by_id(movie.id)

    assert found_movie is not None
    assert found_movie.id == movie.id
    assert found_movie.title == movie_create_request.title
    assert found_movie.tmdb_id == movie_create_request.tmdb_id


@pytest.mark.asyncio
async def test_find_movie_by_tmdb_id(
    beanie_test_db, movie_create_request: MovieCreateRequest
):
    repository = MovieRepository()
    movie = await repository.create_movie(movie_create_request)

    found_movie = await repository.find_movie_by_tmdb_id(movie.tmdb_id)

    assert found_movie is not None
    assert found_movie.id == movie.id
    assert found_movie.title == movie_create_request.title
    assert found_movie.tmdb_id == movie_create_request.tmdb_id


@pytest.mark.asyncio
async def test_update_movie_not_found(
    beanie_test_db, movie_update_request: MovieUpdateRequest
):
    repository = MovieRepository()
    result = await repository.update_movie(
        "507f1f77bcf86cd799439011", movie_update_request
    )
    assert result is None


@pytest.mark.asyncio
async def test_find_movie_by_id_not_found(beanie_test_db):
    repository = MovieRepository()
    result = await repository.find_movie_by_id("507f1f77bcf86cd799439011")
    assert result is None


@pytest.mark.asyncio
async def test_find_movie_by_tmdb_id_not_found(beanie_test_db):
    repository = MovieRepository()
    result = await repository.find_movie_by_tmdb_id(999999999)
    assert result is None


@pytest.mark.asyncio
async def test_create_from_tmdb_data(beanie_test_db):
    from app.schemas.tmdb_schemas import TMDBMovieDetails

    repository = MovieRepository()
    tmdb_data = TMDBMovieDetails(
        id=12345,
        title="Test Movie",
        original_title="Test Movie Original",
        release_date="2023-05-15",
        overview="A test movie overview",
        poster_path="/test/poster.jpg",
        backdrop_path="/test/backdrop.jpg",
        vote_average=7.5,
        vote_count=1000,
        runtime=120,
        budget=50000000,
        revenue=100000000,
        status="Released",
        original_language="en",
        popularity=50.5,
        adult=False,
        genres=[],
        production_companies=[],
        production_countries=[],
        spoken_languages=[],
    )

    movie = await repository.create_from_tmdb_data(tmdb_data)

    assert movie is not None
    assert movie.tmdb_id == 12345
    assert movie.title == "Test Movie"
    assert movie.overview == "A test movie overview"
    assert movie.poster_path == "/test/poster.jpg"
    assert movie.vote_average == 7.5
    assert movie.runtime == 120
    assert movie.original_language == "en"
    assert movie.release_date is not None


@pytest.mark.asyncio
async def test_create_from_tmdb_data_without_release_date(beanie_test_db):
    from app.schemas.tmdb_schemas import TMDBMovieDetails

    repository = MovieRepository()
    tmdb_data = TMDBMovieDetails(
        id=12346,
        title="Test Movie No Date",
        original_title="Test Movie No Date Original",
        release_date="",
        overview="Movie without release date",
        poster_path="/test/poster2.jpg",
        backdrop_path=None,
        vote_average=6.0,
        vote_count=500,
        runtime=90,
        budget=30000000,
        revenue=60000000,
        status="Released",
        original_language="fr",
        popularity=30.0,
        adult=False,
        genres=[],
        production_companies=[],
        production_countries=[],
        spoken_languages=[],
    )

    movie = await repository.create_from_tmdb_data(tmdb_data)

    assert movie is not None
    assert movie.tmdb_id == 12346
    assert movie.release_date is None


@pytest.mark.asyncio
async def test_create_from_tmdb_data_with_invalid_date(beanie_test_db):
    from app.schemas.tmdb_schemas import TMDBMovieDetails

    repository = MovieRepository()
    tmdb_data = TMDBMovieDetails(
        id=12347,
        title="Test Movie Invalid Date",
        original_title="Test Movie Invalid Date Original",
        release_date="invalid-date",
        overview="Movie with invalid date",
        poster_path="/test/poster3.jpg",
        backdrop_path=None,
        vote_average=5.0,
        vote_count=200,
        runtime=100,
        budget=20000000,
        revenue=40000000,
        status="Released",
        original_language="de",
        popularity=20.0,
        adult=False,
        genres=[],
        production_companies=[],
        production_countries=[],
        spoken_languages=[],
    )

    movie = await repository.create_from_tmdb_data(tmdb_data)

    assert movie is not None
    assert movie.tmdb_id == 12347
    assert movie.release_date is None
