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
            movie_id='507f1f77bcf86cd799439011',
            watched_where='cinema',
            date_watched=datetime(2023, 10, 1, tzinfo=UTC).date(),
            viewing_notes="Great movie!",
            tmdb_id=111111,
            poster_path='/path/to/poster.jpg',
    )

    @pytest.fixture
    def movie_create_second_request_same_movie(self) -> LogCreateRequest:
        return LogCreateRequest(
            movie_id='507f1f77bcf86cd799439011',
            watched_where='streaming',
            date_watched=datetime(2023, 10, 2, tzinfo=UTC).date(),
            viewing_notes="Enjoyed it again!",
            tmdb_id=111111,
            poster_path='/path/to/poster.jpg',
    )

    def test_log_creation(self, movie_create_request: LogCreateRequest, user_id: str):
        log = self.log_repository.create_log(user_id, movie_create_request)

        # Assertions
        assert log is not None
        assert log.id is not None
        assert isinstance(log.movie_id, ObjectId)
        assert log.movie_id.__str__() == movie_create_request.movie_id
        assert log.watched_where == movie_create_request.watched_where
        # Handle both datetime and date objects
        log_date = log.date_watched.date() if hasattr(log.date_watched, 'date') else log.date_watched
        assert log_date == movie_create_request.date_watched
        assert log.viewing_notes == movie_create_request.viewing_notes
        assert log.tmdb_id == movie_create_request.tmdb_id
        assert log.poster_path == movie_create_request.poster_path
        assert Log.objects.count() == 1


    def test_log_creation_with_invalid_watched_where(self, user_id: str):
        # This test validates that Pydantic rejects invalid watchedWhere values
        with pytest.raises(Exception):  # Pydantic ValidationError
            LogCreateRequest(
                movie_id='507f1f77bcf86cd799439011',
                watched_where='unknown',  # Invalid value
                date_watched=datetime(2023, 10, 1, tzinfo=UTC).date(),
                tmdb_id=111111,
            )


    def test_find_logs_by_movie_id(self, movie_create_request: LogCreateRequest, user_id: str):
        log = self.log_repository.create_log(user_id, movie_create_request)

        logs = self.log_repository.find_logs_by_movie_id(movie_create_request.movie_id)

        # Helper to extract date from datetime or date
        def get_date(d):
            return d.date() if hasattr(d, 'date') else d

        assert len(logs) == 1
        assert logs[0].id == log.id
        assert logs[0].movie_id == log.movie_id
        assert logs[0].watched_where == log.watched_where
        assert get_date(logs[0].date_watched) == get_date(log.date_watched)
        assert logs[0].viewing_notes == log.viewing_notes
        assert logs[0].tmdb_id == log.tmdb_id

        second_time_log = self.log_repository.create_log(user_id, movie_create_request)

        logs = self.log_repository.find_logs_by_movie_id(movie_create_request.movie_id)

        assert len(logs) == 2
        assert logs[0].id == log.id
        assert logs[1].id == second_time_log.id
        assert logs[0].movie_id == log.movie_id
        assert logs[1].movie_id == second_time_log.movie_id
        assert logs[0].watched_where == log.watched_where
        assert logs[1].watched_where == second_time_log.watched_where
        assert get_date(logs[0].date_watched) == get_date(log.date_watched)
        assert get_date(logs[1].date_watched) == get_date(second_time_log.date_watched)
        assert logs[0].viewing_notes == log.viewing_notes
        assert logs[1].viewing_notes == second_time_log.viewing_notes
        assert logs[0].tmdb_id == log.tmdb_id
        assert logs[1].tmdb_id == second_time_log.tmdb_id

    def test_log_list_without_filters(self, movie_create_request: LogCreateRequest, user_id: str):
        log = self.log_repository.create_log(user_id, movie_create_request)

        log_list_request = LogListRequest(
            sort_by= "dateWatched",
            sort_order= "desc",
            watched_where=None,
            dateWatchedFrom=None,
            dateWatchedTo=None
        )

        logs = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs) == 1
        assert logs[0]['id'] == str(log.id)
        assert str(logs[0]['movieId']) == str(log.movie_id)
        assert logs[0]['watchedWhere'] == log.watched_where
        assert logs[0]['viewingNotes'] == log.viewing_notes
        assert logs[0]['tmdbId'] == log.tmdb_id


    def test_log_list_for_one_year(self, movie_create_request: LogCreateRequest, user_id: str):
        log = self.log_repository.create_log(user_id, movie_create_request)

        log_list_request = LogListRequest(
            sort_by= "dateWatched",
            sort_order= "desc",
            watched_where=None,
            dateWatchedFrom=datetime(2023, 1, 1, tzinfo=UTC).date(),
            dateWatchedTo=datetime(2023, 12, 31, tzinfo=UTC).date()
        )

        logs = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs) == 1
        assert logs[0]['id'] == str(log.id)
        assert str(logs[0]['movieId']) == str(log.movie_id)
        assert logs[0]['watchedWhere'] == log.watched_where
        assert logs[0]['viewingNotes'] == log.viewing_notes
        assert logs[0]['tmdbId'] == log.tmdb_id

        log_list_request_2024 = LogListRequest(
            sort_by= "dateWatched",
            sort_order= "desc",
            watched_where=None,
            dateWatchedFrom=datetime(2024, 1, 1, tzinfo=UTC).date(),
            dateWatchedTo=datetime(2024, 12, 31, tzinfo=UTC).date()
        )

        logs_2024 = self.log_repository.find_logs_by_user_id(user_id, log_list_request_2024)

        assert len(logs_2024) == 0


    def test_sort_by_date_watched(self, movie_create_request: LogCreateRequest, user_id: str):
        log1 = self.log_repository.create_log(user_id, movie_create_request)

        movie_create_request.date_watched = datetime(2023, 10, 2, tzinfo=UTC).date()
        log2 = self.log_repository.create_log(user_id, movie_create_request)

        log_list_request = LogListRequest(
            sort_by= "dateWatched",
            sort_order= "desc",
            watched_where=None,
            dateWatchedFrom=None,
            dateWatchedTo=None
        )

        logs_desc = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs_desc) == 2
        assert logs_desc[0]['id'] == str(log2.id)
        assert logs_desc[1]['id'] == str(log1.id)

        log_list_request.sort_order = "asc"

        logs_asc = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs_asc) == 2
        assert logs_asc[0]['id'] == str(log1.id)
        assert logs_asc[1]['id'] == str(log2.id)


    def test_log_list_with_watched_where_filter(self, movie_create_request: LogCreateRequest, movie_create_second_request_same_movie: LogCreateRequest, user_id: str):
        log1 = self.log_repository.create_log(user_id, movie_create_request)
        log2 = self.log_repository.create_log(user_id, movie_create_second_request_same_movie)

        log_list_request = LogListRequest(
            sort_by= "dateWatched",
            sort_order= "desc",
            watched_where="cinema",
            dateWatchedFrom=None,
            dateWatchedTo=None
        )

        logs = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs) == 1
        assert logs[0]['id'] == str(log1.id)
        assert str(logs[0]['movieId']) == str(log1.movie_id)
        assert logs[0]['watchedWhere'] == log1.watched_where
        assert logs[0]['viewingNotes'] == log1.viewing_notes
        assert logs[0]['tmdbId'] == log1.tmdb_id

        log_list_request.watched_where = "streaming"

        logs = self.log_repository.find_logs_by_user_id(user_id, log_list_request)

        assert len(logs) == 1
        assert logs[0]['id'] == str(log2.id)
        assert str(logs[0]['movieId']) == str(log2.movie_id)
        assert logs[0]['watchedWhere'] == log2.watched_where
        assert logs[0]['viewingNotes'] == log2.viewing_notes
        assert logs[0]['tmdbId'] == log2.tmdb_id

    def test_find_log_by_id_not_found(self, user_id: str):
        """Test find_log_by_id returns None when log not found."""
        non_existent_id = str(ObjectId())
        
        result = self.log_repository.find_log_by_id(non_existent_id, user_id)
        
        assert result is None

    def test_find_log_by_id_success(self, movie_create_request: LogCreateRequest, user_id: str):
        """Test find_log_by_id returns log when found."""
        log = self.log_repository.create_log(user_id, movie_create_request)
        
        result = self.log_repository.find_log_by_id(str(log.id), user_id)
        
        assert result is not None
        assert result.id == log.id

    def test_update_log_not_found(self, user_id: str):
        """Test update_log returns None when log not found."""
        from app.schemas.log_schemas import LogUpdateRequest
        
        non_existent_id = str(ObjectId())
        update_request = LogUpdateRequest(viewing_notes="Updated notes")
        
        result = self.log_repository.update_log(non_existent_id, user_id, update_request)
        
        assert result is None

    def test_update_log_success(self, movie_create_request: LogCreateRequest, user_id: str):
        """Test update_log updates log successfully."""
        from app.schemas.log_schemas import LogUpdateRequest
        
        log = self.log_repository.create_log(user_id, movie_create_request)
        update_request = LogUpdateRequest(viewing_notes="Updated notes", watched_where="streaming")
        
        result = self.log_repository.update_log(str(log.id), user_id, update_request)
        
        assert result is not None
        assert result.viewing_notes == "Updated notes"
        assert result.watched_where == "streaming"

    def test_delete_log_not_found(self, user_id: str):
        """Test delete_log returns False when log not found."""
        non_existent_id = str(ObjectId())
        
        result = self.log_repository.delete_log(non_existent_id, user_id)
        
        assert result is False

    def test_delete_log_success(self, movie_create_request: LogCreateRequest, user_id: str):
        """Test delete_log marks log as deleted."""
        log = self.log_repository.create_log(user_id, movie_create_request)
        
        result = self.log_repository.delete_log(str(log.id), user_id)
        
        assert result is True
        # Verify the log is marked as deleted
        updated_log = Log.objects(id=log.id).first()
        assert updated_log.deleted is True

    def test_find_logs_by_user_id_empty(self, user_id: str):
        """Test find_logs_by_user_id returns empty list when no logs exist."""
        log_list_request = LogListRequest(
            sort_by="dateWatched",
            sort_order="desc"
        )
        
        logs = self.log_repository.find_logs_by_user_id(user_id, log_list_request)
        
        assert logs == []

    def test_find_logs_by_user_id_without_request(self, movie_create_request: LogCreateRequest, user_id: str):
        """Test find_logs_by_user_id with no request parameter uses defaults."""
        log = self.log_repository.create_log(user_id, movie_create_request)
        
        # Call without request parameter
        logs = self.log_repository.find_logs_by_user_id(user_id)
        
        assert len(logs) == 1
        assert logs[0]['id'] == str(log.id)

    def test_find_logs_by_movie_id_with_user_filter(self, movie_create_request: LogCreateRequest, user_id: str):
        """Test find_logs_by_movie_id with user_id filter."""
        log = self.log_repository.create_log(user_id, movie_create_request)
        other_user_id = str(ObjectId())
        
        # With matching user_id
        logs = self.log_repository.find_logs_by_movie_id(movie_create_request.movie_id, user_id)
        assert len(logs) == 1
        
        # With non-matching user_id
        logs = self.log_repository.find_logs_by_movie_id(movie_create_request.movie_id, other_user_id)
        assert len(logs) == 0

