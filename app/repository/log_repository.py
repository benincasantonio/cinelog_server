from app.models.log import Log
from app.schemas.log_schemas import LogCreateRequest, LogListRequest

class LogRepository:
    def __init__(self):
        pass

    @staticmethod
    def create_log(create_log_request: LogCreateRequest) -> Log:
        """
        Create a new log entry in the database.
        """
        log_data = create_log_request.model_dump()
        log = Log(**log_data)
        log.save()
        return log

    @staticmethod
    def find_logs_by_movie_id(movie_id: str) -> list[Log]:
        """
        Find all log entries for a specific movie by its ID.
        """
        return Log.objects(movieId=movie_id).all()

    @staticmethod
    def get_log_list(request: LogListRequest) -> dict:
        """
        Get a paginated list of log entries with optional sorting.
        """
        query = Log.objects()

        if request.watchedWhere is not None:
            query = query.filter(watchedWhere=request.watchedWhere)

        if request.dateWatchedFrom is not None:
            query = query.filter(dateWatched__gte=request.dateWatchedFrom)

        if request.dateWatchedTo is not None:
            query = query.filter(dateWatched__lte=request.dateWatchedTo)

        sort_order = '-' + request.sortBy if request.sortOrder == 'desc' else request.sortBy

        query = query.order_by(sort_order)

        total_count = query.count()
        logs = query.skip((request.page - 1) * request.pageSize).limit(request.pageSize)

        return {
            "logs": list(logs),
            "totalCount": total_count,
            "page": request.page,
            "pageSize": request.pageSize
        }




