from bson import ObjectId
from mongoengine import disconnect, connect, ValidationError
import mongomock
from app.models.log import Log
import pytest

from app.repository.log_repository import LogRepository
from app.schemas.log_schemas import LogCreateRequest, LogListRequest
from datetime import datetime, UTC

class TestLogRepository:
    log_repository: LogRepository


    @pytest.fixture(autouse=True)
    def setup_repository(self):
        self.log_repository = LogRepository()


    @pytest.fixture(scope="module", autouse=True)
    def setup_and_teardown(self):
        # Disconnect from any existing connections first
        disconnect()
        # Connect to a test database using mongomock
        connect('mongoenginetest', host='localhost', mongo_client_class=mongomock.MongoClient)
        yield
        # Disconnect from the test database
        disconnect()

    @pytest.fixture(autouse=True)
    def clear_database(self):
        Log.objects.delete()

    @pytest.fixture
    def movie_create_request(self) -> LogCreateRequest:
        return LogCreateRequest(
            movieId='507f1f77bcf86cd799439011',
            watchedWhere='cinema',
            dateWatched=datetime(2023, 10, 1, tzinfo=UTC),
            rating=10,
            comment="Great movie!",
            tmdbId=111111,
            posterPath='/path/to/poster.jpg',
    )

    @pytest.fixture
    def movie_create_second_request_same_movie(self) -> LogCreateRequest:
        return LogCreateRequest(
            movieId='507f1f77bcf86cd799439011',
            watchedWhere='streaming',
            dateWatched=datetime(2023, 10, 2, tzinfo=UTC),
            rating=8,
            comment="Enjoyed it again!",
            tmdbId=111111,
            posterPath='/path/to/poster.jpg',
    )

    def test_log_creation(self, movie_create_request: LogCreateRequest):
        log = self.log_repository.create_log(movie_create_request)

        # Assertions
        assert log is not None
        assert log.id is not None
        assert isinstance(log.movieId, ObjectId)
        assert log.movieId.__str__() == movie_create_request.movieId
        assert log.watchedWhere == movie_create_request.watchedWhere
        assert log.dateWatched == movie_create_request.dateWatched
        assert log.rating == movie_create_request.rating
        assert log.comment == movie_create_request.comment
        assert log.tmdbId == movie_create_request.tmdbId
        assert log.posterPath == movie_create_request.posterPath
        assert Log.objects.count() == 1


    def test_log_creation_with_invalid_rating(self, movie_create_request: LogCreateRequest):
        movie_create_request.rating = 11
        with pytest.raises(ValidationError, match="Integer value is too large: \['rating'\]"):
            self.log_repository.create_log(movie_create_request)


    def test_find_logs_by_movie_id(self, movie_create_request: LogCreateRequest):
        log = self.log_repository.create_log(movie_create_request)

        logs = self.log_repository.find_logs_by_movie_id(movie_create_request.movieId)

        assert len(logs) == 1
        assert logs[0].id == log.id
        assert logs[0].movieId == log.movieId
        assert logs[0].watchedWhere == log.watchedWhere
        assert logs[0].dateWatched.date() == log.dateWatched
        assert logs[0].rating == log.rating
        assert logs[0].comment == log.comment
        assert logs[0].tmdbId == log.tmdbId

        second_time_log = self.log_repository.create_log(movie_create_request)

        logs = self.log_repository.find_logs_by_movie_id(movie_create_request.movieId)

        assert len(logs) == 2
        assert logs[0].id == log.id
        assert logs[1].id == second_time_log.id
        assert logs[0].movieId == log.movieId
        assert logs[1].movieId == second_time_log.movieId
        assert logs[0].watchedWhere == log.watchedWhere
        assert logs[1].watchedWhere == second_time_log.watchedWhere
        assert logs[0].dateWatched.date() == log.dateWatched
        assert logs[1].dateWatched.date() == second_time_log.dateWatched
        assert logs[0].rating == log.rating
        assert logs[1].rating == second_time_log.rating
        assert logs[0].comment == log.comment
        assert logs[1].comment == second_time_log.comment
        assert logs[0].tmdbId == log.tmdbId
        assert logs[1].tmdbId == second_time_log.tmdbId

    def test_log_list_without_filters(self, movie_create_request: LogCreateRequest):
        log = self.log_repository.create_log(movie_create_request)

        log_list_request = LogListRequest(
            page= 1,
            pageSize= 10,
            sortBy= "dateWatched",
            sortOrder= "desc",
            watchedWhere=None,
            dateWatchedFrom=None,
            dateWatchedTo=None
        )

        log_list_response = self.log_repository.get_log_list(log_list_request)

        assert log_list_response['totalCount'] == 1
        assert len(log_list_response['logs']) == 1
        assert log_list_response['logs'][0].id == log.id
        assert log_list_response['logs'][0].movieId == log.movieId
        assert log_list_response['logs'][0].watchedWhere == log.watchedWhere
        assert log_list_response['logs'][0].dateWatched.date() == log.dateWatched
        assert log_list_response['logs'][0].rating == log.rating
        assert log_list_response['logs'][0].comment == log.comment
        assert log_list_response['logs'][0].tmdbId == log.tmdbId


    def test_log_list_for_one_year(self, movie_create_request: LogCreateRequest):
        log = self.log_repository.create_log(movie_create_request)

        log_list_request = LogListRequest(
            page= 1,
            pageSize= 10,
            sortBy= "dateWatched",
            sortOrder= "desc",
            watchedWhere=None,
            dateWatchedFrom=datetime(2023, 1, 1, tzinfo=UTC),
            dateWatchedTo=datetime(2023, 12, 31, tzinfo=UTC)
        )

        log_list_response = self.log_repository.get_log_list(log_list_request)

        assert log_list_response['totalCount'] == 1
        assert len(log_list_response['logs']) == 1
        assert log_list_response['logs'][0].id == log.id
        assert log_list_response['logs'][0].movieId == log.movieId
        assert log_list_response['logs'][0].watchedWhere == log.watchedWhere
        assert log_list_response['logs'][0].dateWatched.date() == log.dateWatched
        assert log_list_response['logs'][0].rating == log.rating
        assert log_list_response['logs'][0].comment == log.comment
        assert log_list_response['logs'][0].tmdbId == log.tmdbId

        log_list_request_2024 = LogListRequest(
            page= 1,
            pageSize= 10,
            sortBy= "dateWatched",
            sortOrder= "desc",
            watchedWhere=None,
            dateWatchedFrom=datetime(2024, 1, 1, tzinfo=UTC),
            dateWatchedTo=datetime(2024, 12, 31, tzinfo=UTC)
        )

        log_list_response_2024 = self.log_repository.get_log_list(log_list_request_2024)

        assert log_list_response_2024['totalCount'] == 0


    def test_sort_by_date_watched(self, movie_create_request: LogCreateRequest):
        log1 = self.log_repository.create_log(movie_create_request)

        movie_create_request.dateWatched = datetime(2023, 10, 2, tzinfo=UTC)
        log2 = self.log_repository.create_log(movie_create_request)

        log_list_request = LogListRequest(
            page= 1,
            pageSize= 10,
            sortBy= "dateWatched",
            sortOrder= "desc",
            watchedWhere=None,
            dateWatchedFrom=None,
            dateWatchedTo=None
        )

        log_list_response_desc = self.log_repository.get_log_list(log_list_request)

        assert log_list_response_desc['totalCount'] == 2
        assert len(log_list_response_desc['logs']) == 2
        assert log_list_response_desc['logs'][0].id == log2.id
        assert log_list_response_desc['logs'][1].id == log1.id

        log_list_request.sortOrder = "asc"

        log_list_response_asc = self.log_repository.get_log_list(log_list_request)

        assert log_list_response_asc['totalCount'] == 2
        assert len(log_list_response_asc['logs']) == 2
        assert log_list_response_asc['logs'][0].id == log1.id
        assert log_list_response_asc['logs'][1].id == log2.id


    def test_log_list_with_watched_where_filter(self, movie_create_request: LogCreateRequest, movie_create_second_request_same_movie: LogCreateRequest):
        log1 = self.log_repository.create_log(movie_create_request)
        log2 = self.log_repository.create_log(movie_create_second_request_same_movie)

        log_list_request = LogListRequest(
            page= 1,
            pageSize= 10,
            sortBy= "dateWatched",
            sortOrder= "desc",
            watchedWhere="cinema",
            dateWatchedFrom=None,
            dateWatchedTo=None
        )

        log_list_response = self.log_repository.get_log_list(log_list_request)

        assert log_list_response['totalCount'] == 1
        assert len(log_list_response['logs']) == 1
        assert log_list_response['logs'][0].id == log1.id
        assert log_list_response['logs'][0].movieId == log1.movieId
        assert log_list_response['logs'][0].watchedWhere == log1.watchedWhere
        assert log_list_response['logs'][0].dateWatched.date() == log1.dateWatched
        assert log_list_response['logs'][0].rating == log1.rating
        assert log_list_response['logs'][0].comment == log1.comment
        assert log_list_response['logs'][0].tmdbId == log1.tmdbId

        log_list_request.watchedWhere = "streaming"

        log_list_response = self.log_repository.get_log_list(log_list_request)

        assert log_list_response['totalCount'] == 1
        assert len(log_list_response['logs']) == 1
        assert log_list_response['logs'][0].id == log2.id
        assert log_list_response['logs'][0].movieId == log2.movieId
        assert log_list_response['logs'][0].watchedWhere == log2.watchedWhere
        assert log_list_response['logs'][0].dateWatched.date() == log2.dateWatched
        assert log_list_response['logs'][0].rating == log2.rating
        assert log_list_response['logs'][0].comment == log2.comment
        assert log_list_response['logs'][0].tmdbId == log2.tmdbId






