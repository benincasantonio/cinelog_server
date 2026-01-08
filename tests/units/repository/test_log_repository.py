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
    def user_id(self) -> str:
        return str(ObjectId())

    @pytest.fixture
    def movie_create_request(self) -> LogCreateRequest:
        return LogCreateRequest(
            movieId='507f1f77bcf86cd799439011',
            watchedWhere='cinema',
            dateWatched=datetime(2023, 10, 1, tzinfo=UTC).date(),
            viewingNotes="Great movie!",
            tmdbId=111111,
            posterPath='/path/to/poster.jpg',
    )

    @pytest.fixture
    def movie_create_second_request_same_movie(self) -> LogCreateRequest:
        return LogCreateRequest(
            movieId='507f1f77bcf86cd799439011',
            watchedWhere='streaming',
            dateWatched=datetime(2023, 10, 2, tzinfo=UTC).date(),
            viewingNotes="Enjoyed it again!",
            tmdbId=111111,
            posterPath='/path/to/poster.jpg',
    )

    def test_log_creation(self, movie_create_request: LogCreateRequest, user_id: str):
        log = self.log_repository.create_log(user_id, movie_create_request)

        # Assertions
        assert log is not None
        assert log.id is not None
        assert isinstance(log.movieId, ObjectId)
        assert log.movieId.__str__() == movie_create_request.movieId
        assert log.watchedWhere == movie_create_request.watchedWhere
        # Handle both datetime and date objects
        log_date = log.dateWatched.date() if hasattr(log.dateWatched, 'date') else log.dateWatched
        assert log_date == movie_create_request.dateWatched
        assert log.viewingNotes == movie_create_request.viewingNotes
        assert log.tmdbId == movie_create_request.tmdbId
        assert log.posterPath == movie_create_request.posterPath
        assert Log.objects.count() == 1


    def test_log_creation_with_invalid_watched_where(self, user_id: str):
        # This test validates that Pydantic rejects invalid watchedWhere values
        with pytest.raises(Exception):  # Pydantic ValidationError
            LogCreateRequest(
                movieId='507f1f77bcf86cd799439011',
                watchedWhere='unknown',  # Invalid value
                dateWatched=datetime(2023, 10, 1, tzinfo=UTC).date(),
                tmdbId=111111,
            )


    def test_find_logs_by_movie_id(self, movie_create_request: LogCreateRequest, user_id: str):
        log = self.log_repository.create_log(user_id, movie_create_request)

        logs = self.log_repository.find_logs_by_movie_id(movie_create_request.movieId)

        # Helper to extract date from datetime or date
        def get_date(d):
            return d.date() if hasattr(d, 'date') else d

        assert len(logs) == 1
        assert logs[0].id == log.id
        assert logs[0].movieId == log.movieId
        assert logs[0].watchedWhere == log.watchedWhere
        assert get_date(logs[0].dateWatched) == get_date(log.dateWatched)
        assert logs[0].viewingNotes == log.viewingNotes
        assert logs[0].tmdbId == log.tmdbId

        second_time_log = self.log_repository.create_log(user_id, movie_create_request)

        logs = self.log_repository.find_logs_by_movie_id(movie_create_request.movieId)

        assert len(logs) == 2
        assert logs[0].id == log.id
        assert logs[1].id == second_time_log.id
        assert logs[0].movieId == log.movieId
        assert logs[1].movieId == second_time_log.movieId
        assert logs[0].watchedWhere == log.watchedWhere
        assert logs[1].watchedWhere == second_time_log.watchedWhere
        assert get_date(logs[0].dateWatched) == get_date(log.dateWatched)
        assert get_date(logs[1].dateWatched) == get_date(second_time_log.dateWatched)
        assert logs[0].viewingNotes == log.viewingNotes
        assert logs[1].viewingNotes == second_time_log.viewingNotes
        assert logs[0].tmdbId == log.tmdbId
        assert logs[1].tmdbId == second_time_log.tmdbId

    def test_log_list_without_filters(self, movie_create_request: LogCreateRequest, user_id: str):
        log = self.log_repository.create_log(user_id, movie_create_request)

        log_list_request = LogListRequest(
            sortBy= "dateWatched",
            sortOrder= "desc",
            watchedWhere=None,
            dateWatchedFrom=None,
            dateWatchedTo=None
        )

        logs = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs) == 1
        assert logs[0]['id'] == str(log.id)
        assert str(logs[0]['movieId']) == str(log.movieId)
        assert logs[0]['watchedWhere'] == log.watchedWhere
        assert logs[0]['viewingNotes'] == log.viewingNotes
        assert logs[0]['tmdbId'] == log.tmdbId


    def test_log_list_for_one_year(self, movie_create_request: LogCreateRequest, user_id: str):
        log = self.log_repository.create_log(user_id, movie_create_request)

        log_list_request = LogListRequest(
            sortBy= "dateWatched",
            sortOrder= "desc",
            watchedWhere=None,
            dateWatchedFrom=datetime(2023, 1, 1, tzinfo=UTC).date(),
            dateWatchedTo=datetime(2023, 12, 31, tzinfo=UTC).date()
        )

        logs = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs) == 1
        assert logs[0]['id'] == str(log.id)
        assert str(logs[0]['movieId']) == str(log.movieId)
        assert logs[0]['watchedWhere'] == log.watchedWhere
        assert logs[0]['viewingNotes'] == log.viewingNotes
        assert logs[0]['tmdbId'] == log.tmdbId

        log_list_request_2024 = LogListRequest(
            sortBy= "dateWatched",
            sortOrder= "desc",
            watchedWhere=None,
            dateWatchedFrom=datetime(2024, 1, 1, tzinfo=UTC).date(),
            dateWatchedTo=datetime(2024, 12, 31, tzinfo=UTC).date()
        )

        logs_2024 = self.log_repository.find_logs_by_user_id(user_id, log_list_request_2024)

        assert len(logs_2024) == 0


    def test_sort_by_date_watched(self, movie_create_request: LogCreateRequest, user_id: str):
        log1 = self.log_repository.create_log(user_id, movie_create_request)

        movie_create_request.dateWatched = datetime(2023, 10, 2, tzinfo=UTC).date()
        log2 = self.log_repository.create_log(user_id, movie_create_request)

        log_list_request = LogListRequest(
            sortBy= "dateWatched",
            sortOrder= "desc",
            watchedWhere=None,
            dateWatchedFrom=None,
            dateWatchedTo=None
        )

        logs_desc = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs_desc) == 2
        assert logs_desc[0]['id'] == str(log2.id)
        assert logs_desc[1]['id'] == str(log1.id)

        log_list_request.sortOrder = "asc"

        logs_asc = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs_asc) == 2
        assert logs_asc[0]['id'] == str(log1.id)
        assert logs_asc[1]['id'] == str(log2.id)


    def test_log_list_with_watched_where_filter(self, movie_create_request: LogCreateRequest, movie_create_second_request_same_movie: LogCreateRequest, user_id: str):
        log1 = self.log_repository.create_log(user_id, movie_create_request)
        log2 = self.log_repository.create_log(user_id, movie_create_second_request_same_movie)

        log_list_request = LogListRequest(
            sortBy= "dateWatched",
            sortOrder= "desc",
            watchedWhere="cinema",
            dateWatchedFrom=None,
            dateWatchedTo=None
        )

        logs = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs) == 1
        assert logs[0]['id'] == str(log1.id)
        assert str(logs[0]['movieId']) == str(log1.movieId)
        assert logs[0]['watchedWhere'] == log1.watchedWhere
        assert logs[0]['viewingNotes'] == log1.viewingNotes
        assert logs[0]['tmdbId'] == log1.tmdbId

        log_list_request.watchedWhere = "streaming"

        logs = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs) == 1
        assert logs[0]['id'] == str(log2.id)
        assert str(logs[0]['movieId']) == str(log2.movieId)
        assert logs[0]['watchedWhere'] == log2.watchedWhere
        assert logs[0]['viewingNotes'] == log2.viewingNotes
        assert logs[0]['tmdbId'] == log2.tmdbId
