from datetime import datetime

from app.models.log import Log
from app.models.movie import Movie
from app.models.movie_rating import MovieRating
from app.schemas.log_schemas import LogCreateRequest, LogListRequest, LogUpdateRequest
from app.utils.datetime_utils import date_end_utc, date_start_utc, to_utc_datetime
from app.utils.object_id_utils import to_object_id
from beanie import SortDirection


class LogRepository:
    @staticmethod
    async def create_log(user_id: str, create_log_request: LogCreateRequest) -> Log:
        """
        Create a new log entry in the database.
        """
        user_object_id = to_object_id(user_id)
        movie_object_id = to_object_id(create_log_request.movie_id)
        if user_object_id is None or movie_object_id is None:
            raise ValueError("Invalid user_id or movie_id")

        log_data = create_log_request.model_dump(exclude_none=True)
        log_data["user_id"] = user_object_id
        log_data["movie_id"] = movie_object_id
        log_data["date_watched"] = to_utc_datetime(create_log_request.date_watched)

        log = Log(**log_data)
        await log.insert()
        return log

    @staticmethod
    async def find_log_by_id(log_id: str, user_id: str) -> Log | None:
        """
        Find a log entry by its ID, ensuring it belongs to the user.
        """
        log_object_id = to_object_id(log_id)
        user_object_id = to_object_id(user_id)
        if log_object_id is None or user_object_id is None:
            return None
        return await Log.find_one(
            Log.active_filter({"_id": log_object_id, "userId": user_object_id})
        )

    @staticmethod
    async def update_log(
        log_id: str, user_id: str, update_request: LogUpdateRequest
    ) -> Log | None:
        """
        Update an existing log entry.
        """
        log = await LogRepository.find_log_by_id(log_id, user_id)
        if not log:
            return None

        update_data = update_request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "date_watched" and value is not None:
                value = to_utc_datetime(value)
            setattr(log, field, value)

        await log.save()
        return log

    @staticmethod
    async def find_logs_by_user_id(
        user_id: str, request: LogListRequest | None = None
    ) -> list[dict]:
        """
        Find all log entries for a specific user with optional filtering and sorting.
        Returns a list of dictionaries containing log data with joined movie data.
        """
        user_object_id = to_object_id(user_id)
        if user_object_id is None:
            return []

        filters: dict = Log.active_filter({"userId": user_object_id})
        date_filters: dict = {}

        if request:
            if request.watched_where is not None:
                filters["watchedWhere"] = request.watched_where
            if request.date_watched_from is not None:
                date_filters["$gte"] = date_start_utc(request.date_watched_from)
            if request.date_watched_to is not None:
                date_filters["$lte"] = date_end_utc(request.date_watched_to)

        if date_filters:
            filters["dateWatched"] = date_filters

        sort_spec: list[tuple[str, SortDirection]] = [
            ("dateWatched", SortDirection.DESCENDING)
        ]
        sort_direction: SortDirection = SortDirection.DESCENDING
        if request:
            sort_direction = (
                SortDirection.DESCENDING
                if request.sort_order == "desc"
                else SortDirection.ASCENDING
            )
            if request.sort_by == "watchedWhere":
                sort_spec = [
                    ("watchedWhere", sort_direction),
                    ("createdAt", sort_direction),
                ]
            else:
                sort_spec = [
                    ("dateWatched", sort_direction),
                    ("createdAt", sort_direction),
                ]

        logs = await Log.find(filters).sort(sort_spec).to_list()
        if not logs:
            return []

        movie_ids = list({str(log.movie_id) for log in logs})
        object_movie_ids = list({to_object_id(movie_id) for movie_id in movie_ids})
        object_movie_ids = [movie_id for movie_id in object_movie_ids if movie_id]

        movies = await Movie.find(
            Movie.active_filter({"_id": {"$in": movie_ids}})
        ).to_list()
        movie_ratings = await MovieRating.find(
            MovieRating.active_filter(
                {"userId": user_object_id, "movieId": {"$in": object_movie_ids}}
            )
        ).to_list()

        rating_map: dict[str, float] = {
            str(rating.movie_id): rating.rating for rating in movie_ratings
        }
        movie_map: dict[str, Movie] = {str(movie.id): movie for movie in movies}

        result: list[dict] = []
        for log in logs:
            log_dict = {
                "id": str(log.id),
                "movieId": str(log.movie_id),
                "tmdbId": log.tmdb_id,
                "dateWatched": (
                    log.date_watched.date()
                    if isinstance(log.date_watched, datetime)
                    else log.date_watched
                ),
                "viewingNotes": log.viewing_notes,
                "posterPath": log.poster_path,
                "watchedWhere": log.watched_where,
            }
            movie_rating = rating_map.get(str(log.movie_id))
            if movie_rating is not None:
                log_dict["movieRating"] = movie_rating

            movie = movie_map.get(str(log.movie_id))
            if movie:
                log_dict["movie"] = movie

            result.append(log_dict)

        return result

    @staticmethod
    async def find_logs_by_movie_id(
        movie_id: str, user_id: str | None = None
    ) -> list[Log]:
        """
        Find all log entries for a specific movie by its ID.
        Optionally filter by user_id.
        """
        movie_object_id = to_object_id(movie_id)
        if movie_object_id is None:
            return []

        query_params: dict = Log.active_filter({"movieId": movie_object_id})
        if user_id:
            user_object_id = to_object_id(user_id)
            if user_object_id is None:
                return []
            query_params["userId"] = user_object_id

        return await Log.find(query_params).to_list()

    @staticmethod
    async def delete_log(log_id: str, user_id: str) -> bool:
        """
        Delete a log entry (soft delete).
        """
        log = await LogRepository.find_log_by_id(log_id, user_id)
        if not log:
            return False

        log.deleted = True
        await log.save()
        return True
