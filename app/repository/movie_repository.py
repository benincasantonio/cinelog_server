from datetime import datetime, UTC
from pymongo.errors import DuplicateKeyError

from app.models.movie import Movie
from app.schemas.movie_schemas import MovieCreateRequest, MovieUpdateRequest
from app.schemas.tmdb_schemas import TMDBMovieDetails


class MovieRepository:
    """Repository class for movie-related operations."""

    @staticmethod
    async def create_movie(request: MovieCreateRequest) -> Movie:
        """Create a new movie in the database."""

        movie_data = request.model_dump()
        movie = Movie(**movie_data)
        await movie.insert()
        return movie

    @staticmethod
    async def update_movie(id: str, request: MovieUpdateRequest) -> None:
        """Update a movie in the database."""

        movie = await MovieRepository.find_movie_by_id(id)

        if not movie:
            return None

        movie.title = request.title
        movie.updated_at = datetime.now(UTC)
        await movie.save()

    @staticmethod
    async def find_movie_by_id(movie_id: str) -> Movie | None:
        """Find a movie by ID."""
        return await Movie.find_one(Movie.active_filter({"_id": movie_id}))

    @staticmethod
    async def find_movie_by_tmdb_id(tmdb_id: int) -> Movie | None:
        """Find a movie by TMDB ID."""
        return await Movie.find_one(
            Movie.active_filter({"tmdbId": tmdb_id})
        )

    @staticmethod
    async def create_from_tmdb_data(tmdb_data: TMDBMovieDetails) -> Movie:
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
            await movie.insert()
            return movie
        except DuplicateKeyError:
            existing_movie = await MovieRepository.find_movie_by_tmdb_id(tmdb_data.id)
            if existing_movie is None:
                raise
            return existing_movie
