from mongoengine.errors import NotUniqueError
from app.models.movie import Movie
from app.schemas.movie_schemas import (
    MovieCreateRequest,
    MovieUpdateRequest,
)
from datetime import datetime, UTC

from app.schemas.tmdb_schemas import TMDBMovieDetails


class MovieRepository:
    """Repository class for movie-related operations."""

    @staticmethod
    def create_movie(request: MovieCreateRequest) -> Movie:
        """Create a new movie in the database."""

        movie_data = request.model_dump()
        movie = Movie(**movie_data)
        movie.save()
        return movie

    @staticmethod
    def update_movie(id: str, request: MovieUpdateRequest) -> None:
        """Update a movie in the database."""

        movie = MovieRepository.find_movie_by_id(id)

        if not movie:
            return None

        movie.update(set__title=request.title, set__updated_at=datetime.now(UTC))

    @staticmethod
    def find_movie_by_id(movie_id: str) -> Movie:
        """Find a movie by ID."""
        return Movie.objects(id=movie_id).first()

    @staticmethod
    def find_movie_by_tmdb_id(tmdb_id: int) -> Movie:
        """Find a movie by TMDB ID."""
        return Movie.objects(tmdb_id=tmdb_id).first()

    @staticmethod
    def create_from_tmdb_data(tmdb_data: TMDBMovieDetails) -> Movie:
        """
        Create a movie from TMDB API response data.

        Expected fields in tmdb_data:
        - id (tmdbId)
        - title
        - release_date
        - overview
        - poster_path
        - vote_average
        - runtime
        - original_language
        """
        from datetime import datetime

        # Parse release date if present
        release_date = None
        if tmdb_data.release_date:
            try:
                release_date = datetime.strptime(tmdb_data.release_date, "%Y-%m-%d")
            except ValueError:
                pass  # Keep as None if parsing fails

        movie = Movie(
            tmdb_id=tmdb_data.id,
            title=tmdb_data.title,
            release_date=release_date,
            overview=tmdb_data.overview,
            poster_path=tmdb_data.poster_path,
            vote_average=tmdb_data.vote_average,
            runtime=tmdb_data.runtime,
            original_language=tmdb_data.original_language,
        )

        try:
            movie.save()
            return movie
        except NotUniqueError:
            return MovieRepository.find_movie_by_tmdb_id(tmdb_data.id)
