from app.models.log import Log
from app.models.movie import Movie
from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest, LogListRequest
from bson import ObjectId


class LogRepository:
    def __init__(self):
        pass

    @staticmethod
    def create_log(user_id: str, create_log_request: LogCreateRequest) -> Log:
        """
        Create a new log entry in the database.
        """
        log_data = create_log_request.model_dump()
        log_data['userId'] = ObjectId(user_id)
        log = Log(**log_data)
        log.save()
        return log

    @staticmethod
    def find_log_by_id(log_id: str, user_id: str) -> Log:
        """
        Find a log entry by its ID, ensuring it belongs to the user.
        """
        return Log.objects(id=log_id, userId=user_id).first()

    @staticmethod
    def update_log(log_id: str, user_id: str, update_request: LogUpdateRequest) -> Log:
        """
        Update an existing log entry.
        """
        log = LogRepository.find_log_by_id(log_id, user_id)
        if not log:
            return None

        update_data = update_request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(log, field, value)

        log.save()
        return log

    @staticmethod
    def find_logs_by_user_id(user_id: str, request: LogListRequest = None) -> list[dict]:
        """
        Find all log entries for a specific user with optional filtering and sorting.
        Returns a list of dictionaries containing log data with joined movie data.
        """
        query = Log.objects(userId=user_id)

        if request:
            # Apply filters
            if request.watchedWhere is not None:
                query = query.filter(watchedWhere=request.watchedWhere)

            if request.dateWatchedFrom is not None:
                query = query.filter(dateWatched__gte=request.dateWatchedFrom)

            if request.dateWatchedTo is not None:
                query = query.filter(dateWatched__lte=request.dateWatchedTo)

            # Apply sorting
            if request.sortBy:
                sort_order = '-' + request.sortBy if request.sortOrder == 'desc' else request.sortBy
                query = query.order_by(sort_order)
        else:
            # Default sorting by date watched descending
            query = query.order_by('-dateWatched')

        logs = list(query)
        if not logs:
            return []

        # Fetch related movies
        # Convert ObjectId to string for lookup if necessary, assuming Movie.id is StringField
        movie_ids = list(set([str(log.movieId) for log in logs]))
        movies = Movie.objects(id__in=movie_ids)
        movie_map = {movie.id: movie for movie in movies}

        result = []
        for log in logs:
            log_dict = log.to_mongo().to_dict()
            # Flatten _id
            log_dict['id'] = str(log_dict['_id'])
            # Add movie object
            movie = movie_map.get(str(log.movieId))
            if movie:
                log_dict['movie'] = movie
            
            result.append(log_dict)

        return result

    @staticmethod
    def find_logs_by_movie_id(movie_id: str, user_id: str = None) -> list[Log]:
        """
        Find all log entries for a specific movie by its ID.
        Optionally filter by user_id.
        """
        query_params = {"movieId": movie_id}
        if user_id:
            query_params["userId"] = user_id

        return Log.objects(**query_params).all()

    @staticmethod
    def delete_log(log_id: str, user_id: str) -> bool:
        """
        Delete a log entry (soft delete).
        """
        log = LogRepository.find_log_by_id(log_id, user_id)
        if not log:
            return False

        log.deleted = True
        log.save()
        return True
