from app.models.movie import Movie
from app.schemas.movie_schemas import MovieCreateRequest, MovieResponse, MovieUpdateRequest
from datetime import datetime, UTC


class MovieRepository:
    """Repository class for movie-related operations."""

    def __init__(self):
        pass



    @staticmethod
    def create_movie(request: MovieCreateRequest) -> Movie:
        """Create a new movie in the database."""

        movie_data = request.model_dump()
        movie = Movie(**movie_data)
        movie.save()
        return movie

    @staticmethod
    def update_movie(id: str, request: MovieUpdateRequest) -> None :
        """Update a movie in the database."""

        movie = MovieRepository.find_movie_by_id(id)

        if not movie:
            return None

        movie.update(
            set__title=request.title,
            set__updatedAt=datetime.now(UTC)
        )

    @staticmethod
    def find_movie_by_id(movie_id: str) -> Movie:
        """Find a movie by ID."""
        return Movie.objects(id=movie_id).first()


    @staticmethod
    def find_movie_by_tmdb_id(tmdb_id: int) -> Movie:
        """Find a movie by TMDB ID."""
        return Movie.objects(tmdbId=tmdb_id).first()


