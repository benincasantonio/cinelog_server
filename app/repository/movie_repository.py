"""MongoDB movie repository implementation."""

from datetime import UTC, datetime

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.models.movie import Movie
from app.schemas.movie_schemas import MovieCreateRequest, MovieStats, MovieUpdateRequest
from app.schemas.tmdb_schemas import TMDBMovieDetails


class MovieRepository:
    """MongoDB movie repository — active runtime implementation.

    Pending replacement by ``PostgresMovieRepository`` (in
    ``app/repository/postgres_movie_repository.py``) once mixed-mode FK
    dependencies in ``LogRepository`` and ``MovieRatingRepository`` are
    migrated. ``PostgresMovieRepository`` is intentionally unwired today —
    do not import it from runtime code paths.
    """

    async def create_movie(self, request: MovieCreateRequest) -> Movie:
        """Create a new movie in MongoDB."""

        movie_data = request.model_dump()
        movie = Movie(**movie_data)
        await movie.insert()
        return movie

    async def update_movie(self, movie_id: PydanticObjectId, request: MovieUpdateRequest) -> None:
        """Update an existing movie in MongoDB."""

        movie = await self.find_movie_by_id(movie_id)

        if not movie:
            return None

        movie.title = request.title
        movie.updated_at = datetime.now(UTC)
        await movie.save()

    async def find_movie_by_id(self, movie_id: PydanticObjectId) -> Movie | None:
        """Find a movie by ID."""
        return await Movie.find_one(Movie.active_filter({"_id": movie_id}))

    async def find_movie_by_tmdb_id(self, tmdb_id: int) -> Movie | None:
        """Find a movie by TMDB ID."""
        return await Movie.find_one(Movie.active_filter({"tmdbId": tmdb_id}))

    async def create_from_tmdb_data(self, tmdb_data: TMDBMovieDetails) -> Movie:
        """Create a movie from TMDB details or return existing one on duplicate TMDB ID."""
        release_date = None
        if tmdb_data.release_date:
            try:
                release_date = datetime.strptime(tmdb_data.release_date, "%Y-%m-%d")
            except ValueError:
                pass

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
            existing_movie = await self.find_movie_by_tmdb_id(tmdb_data.id)
            if existing_movie is None:
                raise
            return existing_movie

    async def find_movies_by_ids(self, movie_ids: set[PydanticObjectId]) -> list[Movie]:
        """Find multiple movies by their IDs."""
        return await Movie.find(Movie.active_filter({"_id": {"$in": list(movie_ids)}})).to_list()

    async def get_movie_stats(self, movie_ids: set[PydanticObjectId]) -> MovieStats:
        """Compute movie aggregates for a set of IDs."""
        pipeline = [
            {"$match": {"_id": {"$in": list(movie_ids)}}},
            {
                "$group": {
                    "_id": None,
                    "totalRuntime": {"$sum": "$runtime"},
                }
            },
        ]

        movie_stats = await Movie.aggregate(pipeline, projection_model=MovieStats).to_list(length=1)

        return movie_stats[0] if movie_stats else MovieStats(total_runtime=0)
