from datetime import date

from app.models.log import Log
from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest
from app.schemas.stats_schemas import LogDistributionEntry, LogStats
from app.utils.datetime_utils import date_end_utc, date_start_utc, to_utc_datetime
from app.utils.object_id_utils import to_object_id
from beanie import SortDirection, PydanticObjectId


class LogRepository:
    @staticmethod
    async def create_log(
        user_id: PydanticObjectId, create_log_request: LogCreateRequest
    ) -> Log:
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
    async def find_log_by_id(log_id: str, user_id: PydanticObjectId) -> Log | None:
        """
        Find a log entry by its ID, ensuring it belongs to the user.
        """
        log_object_id = to_object_id(log_id)
        if log_object_id is None or user_id is None:
            return None
        return await Log.find_one(
            Log.active_filter({"_id": log_object_id, "userId": user_id})
        )

    @staticmethod
    async def update_log(
        log_id: str, user_id: PydanticObjectId, update_request: LogUpdateRequest
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
        user_id: PydanticObjectId,
        watched_where: str | None = None,
        date_watched_from: date | None = None,
        date_watched_to: date | None = None,
        sort_by: str = "dateWatched",
        sort_order: str = "desc",
    ):
        """
        Find all log entries for a specific user with optional filtering and sorting.
        Returns a list of dictionaries containing log data with joined movie data.
        """
        filters: dict = Log.active_filter({"userId": user_id})
        date_filters: dict = {}

        if watched_where is not None:
            filters["watchedWhere"] = watched_where
        if date_watched_from is not None:
            date_filters["$gte"] = date_start_utc(date_watched_from)

        if date_watched_to is not None:
            date_filters["$lte"] = date_end_utc(date_watched_to)

        if date_filters:
            filters["dateWatched"] = date_filters

        sort_spec: list[tuple[str, SortDirection]] = [
            ("dateWatched", SortDirection.DESCENDING)
        ]
        sort_direction: SortDirection = (
            SortDirection.DESCENDING
            if sort_order == "desc"
            else SortDirection.ASCENDING
        )
        if sort_by == "watchedWhere":
            sort_spec = [
                ("watchedWhere", sort_direction),
                ("createdAt", sort_direction),
            ]
        else:
            sort_spec = [
                ("dateWatched", sort_direction),
                ("createdAt", sort_direction),
            ]

        return await Log.find(filters).sort(sort_spec).to_list()

    @staticmethod
    async def find_logs_by_movie_id(
        movie_id: str, user_id: PydanticObjectId | None = None
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
            query_params["userId"] = user_id

        return await Log.find(query_params).to_list()

    @staticmethod
    async def delete_log(log_id: str, user_id: PydanticObjectId) -> bool:
        """
        Delete a log entry (soft delete).
        """
        log = await LogRepository.find_log_by_id(log_id, user_id)
        if not log:
            return False

        log.deleted = True
        await log.save()
        return True

    @staticmethod
    async def get_log_stats(
        user_id: PydanticObjectId,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> LogStats:
        """
        Compute log statistics using a single MongoDB aggregation with $facet.
        Returns total watches, unique titles, unique movie IDs, and distribution.
        """
        match_filter: dict = Log.active_filter({"userId": user_id})

        date_filters: dict = {}
        if date_from is not None:
            date_filters["$gte"] = date_start_utc(date_from)
        if date_to is not None:
            date_filters["$lte"] = date_end_utc(date_to)
        if date_filters:
            match_filter["dateWatched"] = date_filters

        pipeline = [
            {"$match": match_filter},
            {
                "$facet": {
                    "summary": [
                        {
                            "$group": {
                                "_id": None,
                                "totalWatches": {"$sum": 1},
                                "uniqueMovieIds": {"$addToSet": "$movieId"},
                            }
                        },
                        {"$addFields": {"uniqueTitles": {"$size": "$uniqueMovieIds"}}},
                    ],
                    "distribution": [
                        {
                            "$group": {
                                "_id": "$watchedWhere",
                                "count": {"$sum": 1},
                            }
                        },
                    ],
                }
            },
        ]

        results = await Log.aggregate(pipeline).to_list(length=1)

        if not results:
            return LogStats()

        result = results[0]
        summary = result.get("summary", [])
        distribution_raw = result.get("distribution", [])

        if not summary:
            return LogStats()

        summary_data = summary[0]

        distribution = [
            LogDistributionEntry(
                watched_where=entry["_id"],
                count=entry["count"],
            )
            for entry in distribution_raw
        ]

        return LogStats(
            total_watches=summary_data.get("totalWatches", 0),
            unique_titles=summary_data.get("uniqueTitles", 0),
            unique_movie_ids=summary_data.get("uniqueMovieIds", []),
            distribution=distribution,
        )
