from datetime import UTC, datetime

from bson import ObjectId
import pytest

from app.models.log import Log
from app.models.movie import Movie
from app.models.movie_rating import MovieRating
from app.repository.log_repository import LogRepository
from app.schemas.log_schemas import LogCreateRequest, LogListRequest, LogUpdateRequest


@pytest.fixture
def log_repository() -> LogRepository:
    return LogRepository()


@pytest.fixture
def user_id() -> str:
    return str(ObjectId())


@pytest.fixture
def movie_id() -> str:
    return str(ObjectId())


@pytest.fixture
async def sample_movie(beanie_test_db, movie_id: str):
    movie = Movie(id=movie_id, tmdb_id=111111, title="Test Movie")
    await movie.insert()
    return movie


@pytest.fixture
def movie_create_request(movie_id: str) -> LogCreateRequest:
    return LogCreateRequest(
        movie_id=movie_id,
        watched_where="cinema",
        date_watched=datetime(2023, 10, 1, tzinfo=UTC).date(),
        viewing_notes="Great movie!",
        tmdb_id=111111,
        poster_path="/path/to/poster.jpg",
    )


@pytest.fixture
def movie_create_second_request_same_movie(movie_id: str) -> LogCreateRequest:
    return LogCreateRequest(
        movie_id=movie_id,
        watched_where="streaming",
        date_watched=datetime(2023, 10, 2, tzinfo=UTC).date(),
        viewing_notes="Enjoyed it again!",
        tmdb_id=111111,
        poster_path="/path/to/poster.jpg",
    )


@pytest.mark.asyncio
async def test_log_creation(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    user_id: str,
):
    log = await log_repository.create_log(user_id, movie_create_request)

    assert log is not None
    assert log.id is not None
    assert str(log.movie_id) == movie_create_request.movie_id
    assert log.watched_where == movie_create_request.watched_where
    log_date = (
        log.date_watched.date()
        if hasattr(log.date_watched, "date")
        else log.date_watched
    )
    assert log_date == movie_create_request.date_watched
    assert log.viewing_notes == movie_create_request.viewing_notes
    assert log.tmdb_id == movie_create_request.tmdb_id
    assert log.poster_path == movie_create_request.poster_path
    assert await Log.find_all().count() == 1


def test_log_creation_with_invalid_watched_where(user_id: str):
    with pytest.raises(Exception):
        LogCreateRequest(
            movie_id="507f1f77bcf86cd799439011",
            watched_where="unknown",
            date_watched=datetime(2023, 10, 1, tzinfo=UTC).date(),
            tmdb_id=111111,
        )


@pytest.mark.asyncio
async def test_find_logs_by_movie_id(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    user_id: str,
):
    log = await log_repository.create_log(user_id, movie_create_request)
    logs = await log_repository.find_logs_by_movie_id(movie_create_request.movie_id)
    assert len(logs) == 1
    assert logs[0].id == log.id

    second_log = await log_repository.create_log(user_id, movie_create_request)
    logs = await log_repository.find_logs_by_movie_id(movie_create_request.movie_id)
    assert len(logs) == 2
    assert logs[0].id == log.id
    assert logs[1].id == second_log.id


@pytest.mark.asyncio
async def test_log_list_without_filters(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    user_id: str,
):
    log = await log_repository.create_log(user_id, movie_create_request)
    log_list_request = LogListRequest(sort_by="dateWatched", sort_order="desc")
    logs = await log_repository.find_logs_by_user_id(user_id, log_list_request)

    assert len(logs) == 1
    assert logs[0]["id"] == str(log.id)
    assert str(logs[0]["movieId"]) == str(log.movie_id)
    assert logs[0]["watchedWhere"] == log.watched_where
    assert logs[0]["viewingNotes"] == log.viewing_notes
    assert logs[0]["tmdbId"] == log.tmdb_id


@pytest.mark.asyncio
async def test_log_list_with_rating_join(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    user_id: str,
):
    log = await log_repository.create_log(user_id, movie_create_request)
    await MovieRating(
        user_id=ObjectId(user_id),
        movie_id=ObjectId(movie_create_request.movie_id),
        tmdb_id=movie_create_request.tmdb_id,
        rating=8,
    ).insert()

    logs = await log_repository.find_logs_by_user_id(
        user_id, LogListRequest(sort_by="dateWatched", sort_order="desc")
    )
    assert len(logs) == 1
    assert logs[0]["movieRating"] == 8
    assert logs[0]["movie"] is not None
    assert logs[0]["id"] == str(log.id)


@pytest.mark.asyncio
async def test_log_list_for_one_year(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    user_id: str,
):
    await log_repository.create_log(user_id, movie_create_request)

    logs = await log_repository.find_logs_by_user_id(
        user_id,
        LogListRequest(
            sort_by="dateWatched",
            sort_order="desc",
            date_watched_from=datetime(2023, 1, 1, tzinfo=UTC).date(),
            date_watched_to=datetime(2023, 12, 31, tzinfo=UTC).date(),
        ),
    )
    assert len(logs) == 1

    logs_2024 = await log_repository.find_logs_by_user_id(
        user_id,
        LogListRequest(
            sort_by="dateWatched",
            sort_order="desc",
            date_watched_from=datetime(2024, 1, 1, tzinfo=UTC).date(),
            date_watched_to=datetime(2024, 12, 31, tzinfo=UTC).date(),
        ),
    )
    assert len(logs_2024) == 0


@pytest.mark.asyncio
async def test_sort_by_date_watched(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    user_id: str,
):
    log1 = await log_repository.create_log(user_id, movie_create_request)
    movie_create_request.date_watched = datetime(2023, 10, 2, tzinfo=UTC).date()
    log2 = await log_repository.create_log(user_id, movie_create_request)

    logs_desc = await log_repository.find_logs_by_user_id(
        user_id, LogListRequest(sort_by="dateWatched", sort_order="desc")
    )
    assert len(logs_desc) == 2
    assert logs_desc[0]["id"] == str(log2.id)
    assert logs_desc[1]["id"] == str(log1.id)

    logs_asc = await log_repository.find_logs_by_user_id(
        user_id, LogListRequest(sort_by="dateWatched", sort_order="asc")
    )
    assert len(logs_asc) == 2
    assert logs_asc[0]["id"] == str(log1.id)
    assert logs_asc[1]["id"] == str(log2.id)


@pytest.mark.asyncio
async def test_log_list_with_watched_where_filter(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    movie_create_second_request_same_movie: LogCreateRequest,
    user_id: str,
):
    log1 = await log_repository.create_log(user_id, movie_create_request)
    log2 = await log_repository.create_log(
        user_id, movie_create_second_request_same_movie
    )

    logs = await log_repository.find_logs_by_user_id(
        user_id,
        LogListRequest(
            sort_by="dateWatched", sort_order="desc", watched_where="cinema"
        ),
    )
    assert len(logs) == 1
    assert logs[0]["id"] == str(log1.id)

    logs = await log_repository.find_logs_by_user_id(
        user_id,
        LogListRequest(
            sort_by="dateWatched", sort_order="desc", watched_where="streaming"
        ),
    )
    assert len(logs) == 1
    assert logs[0]["id"] == str(log2.id)


@pytest.mark.asyncio
async def test_find_log_by_id_not_found(
    beanie_test_db, log_repository: LogRepository, user_id: str
):
    non_existent_id = str(ObjectId())
    result = await log_repository.find_log_by_id(non_existent_id, user_id)
    assert result is None


@pytest.mark.asyncio
async def test_find_log_by_id_success(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    user_id: str,
):
    log = await log_repository.create_log(user_id, movie_create_request)
    result = await log_repository.find_log_by_id(str(log.id), user_id)
    assert result is not None
    assert result.id == log.id


@pytest.mark.asyncio
async def test_update_log_not_found(
    beanie_test_db, log_repository: LogRepository, user_id: str
):
    non_existent_id = str(ObjectId())
    update_request = LogUpdateRequest(viewing_notes="Updated notes")
    result = await log_repository.update_log(non_existent_id, user_id, update_request)
    assert result is None


@pytest.mark.asyncio
async def test_update_log_success(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    user_id: str,
):
    log = await log_repository.create_log(user_id, movie_create_request)
    update_request = LogUpdateRequest(
        viewing_notes="Updated notes", watched_where="streaming"
    )
    result = await log_repository.update_log(str(log.id), user_id, update_request)
    assert result is not None
    assert result.viewing_notes == "Updated notes"
    assert result.watched_where == "streaming"


@pytest.mark.asyncio
async def test_delete_log_not_found(
    beanie_test_db, log_repository: LogRepository, user_id: str
):
    non_existent_id = str(ObjectId())
    result = await log_repository.delete_log(non_existent_id, user_id)
    assert result is False


@pytest.mark.asyncio
async def test_delete_log_success(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    user_id: str,
):
    log = await log_repository.create_log(user_id, movie_create_request)
    result = await log_repository.delete_log(str(log.id), user_id)
    assert result is True
    updated_log = await Log.get(log.id)
    assert updated_log.deleted is True


@pytest.mark.asyncio
async def test_find_logs_by_user_id_empty(
    beanie_test_db, log_repository: LogRepository, user_id: str
):
    logs = await log_repository.find_logs_by_user_id(
        user_id, LogListRequest(sort_by="dateWatched", sort_order="desc")
    )
    assert logs == []


@pytest.mark.asyncio
async def test_find_logs_by_user_id_without_request(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    user_id: str,
):
    log = await log_repository.create_log(user_id, movie_create_request)
    logs = await log_repository.find_logs_by_user_id(user_id)
    assert len(logs) == 1
    assert logs[0]["id"] == str(log.id)


@pytest.mark.asyncio
async def test_find_logs_by_movie_id_with_user_filter(
    beanie_test_db,
    sample_movie,
    log_repository: LogRepository,
    movie_create_request: LogCreateRequest,
    user_id: str,
):
    await log_repository.create_log(user_id, movie_create_request)
    other_user_id = str(ObjectId())

    logs = await log_repository.find_logs_by_movie_id(
        movie_create_request.movie_id, user_id
    )
    assert len(logs) == 1

    logs = await log_repository.find_logs_by_movie_id(
        movie_create_request.movie_id, other_user_id
    )
    assert len(logs) == 0
