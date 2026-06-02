from uuid import UUID

from beanie import PydanticObjectId

from app.repository.movie_repository_protocol import MovieRepositoryProtocol
from app.services.tmdb_service import TMDBService


class MovieService:
    def __init__(
        self,
        movie_repository: MovieRepositoryProtocol,
        tmdb_service: TMDBService | None = None,
    ):
        self.movie_repository = movie_repository
        self.tmdb_service = tmdb_service or TMDBService.get_instance()

    async def get_movie_by_id(self, movie_id: PydanticObjectId | UUID):
        """Find a movie by its ID."""
        return await self.movie_repository.find_movie_by_id(movie_id)

    async def get_movie_by_tmdb_id(self, tmdb_id: int):
        """Find a movie by its TMDB ID."""
        return await self.movie_repository.find_movie_by_tmdb_id(tmdb_id)

    async def find_or_create_movie(self, tmdb_id: int):
        """Find a movie by TMDB ID, or create it if it doesn't exist."""

        movie = await self.movie_repository.find_movie_by_tmdb_id(tmdb_id)

        if movie:
            return movie

        tmdb_data = await self.tmdb_service.get_movie_details(tmdb_id)
        movie = await self.movie_repository.create_from_tmdb_data(tmdb_data)

        return movie
