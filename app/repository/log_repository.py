from app.models.log import Log
from app.models.movie import Movie
from app.models.movie_rating import MovieRating
from app.schemas.log_schemas import LogCreateRequest, LogUpdateRequest, LogListRequest
from bson import ObjectId


class LogRepository:

    @staticmethod
    def create_log(user_id: str, create_log_request: LogCreateRequest) -> Log:
        """
        Create a new log entry in the database.
        """
        log_data = create_log_request.model_dump()
        log_data["user_id"] = ObjectId(user_id)
        log = Log(**log_data)
        log.save()
        return log

    @staticmethod
    def find_log_by_id(log_id: str, user_id: str) -> Log | None:
        """
        Find a log entry by its ID, ensuring it belongs to the user.
        """
        return Log.objects(id=log_id, user_id=user_id).first()

    @staticmethod
    def update_log(log_id: str, user_id: str, update_request: LogUpdateRequest) -> Log | None:
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
    def find_logs_by_user_id(
        user_id: str, request: LogListRequest | None = None
    ) -> list[dict]:
        """
        Find all log entries for a specific user with optional filtering and sorting.
        Returns a list of dictionaries containing log data with joined movie data.
        """
        query = Log.objects(user_id=user_id)

        if request:
            # Apply filters
            if request.watched_where is not None:
                query = query.filter(watched_where=request.watched_where)

            if request.date_watched_from is not None:
                query = query.filter(date_watched__gte=request.date_watched_from)

            if request.date_watched_to is not None:
                query = query.filter(date_watched__lte=request.date_watched_to)

            # Apply sorting
            if request.sort_by:
                sort_order = (
                    "-" + request.sort_by
                    if request.sort_order == "desc"
                    else request.sort_by
                )
                query = query.order_by(sort_order)
        else:
            # Default sorting by date watched descending
            query = query.order_by("-date_watched")

        logs = list(query)
        if not logs:
            return []

        # Fetch related movies
        # Convert ObjectId to string for lookup if necessary, assuming Movie.id is StringField
        movie_ids = list(set([str(log.movie_id) for log in logs]))
        movies = Movie.objects(id__in=movie_ids)
        movie_ratings = MovieRating.objects(user_id=user_id, movie_id__in=movie_ids)
        rating_map = {str(rating.movie_id): rating.rating for rating in movie_ratings}
        movie_map = {movie.id: movie for movie in movies}

        result = []
        for log in logs:
            log_dict = log.to_mongo().to_dict()
            # Flatten _id
            log_dict["id"] = str(log_dict["_id"])
            # Add movie object
            movie = movie_map.get(str(log.movie_id))

            movieRating = rating_map.get(str(log.movie_id))
            if movieRating is not None:
                log_dict["movieRating"] = movieRating

            if movie:
                log_dict["movie"] = movie

            result.append(log_dict)

        return result

    @staticmethod
    def find_logs_by_movie_id(movie_id: str, user_id: str | None = None) -> list[Log]:
        """
        Find all log entries for a specific movie by its ID.
        Optionally filter by user_id.
        """
        query_params = {"movie_id": movie_id}
        if user_id:
            query_params["user_id"] = user_id

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
