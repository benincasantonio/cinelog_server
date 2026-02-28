from app.repository.movie_repository import MovieRepository
from app.services.tmdb_service import TMDBService
from app.models.movie import Movie
import os


class MovieService:
    def __init__(
        self, movie_repository: MovieRepository, tmdb_service: TMDBService
    ):
        self.movie_repository = movie_repository
        self.tmdb_service = tmdb_service or TMDBService(
            api_key=os.getenv("TMDB_API_KEY")
        )

    def get_movie_by_id(self, movie_id: str) -> Movie:
        """
        Find a movie by its ID.

        Args:
            movie_id: The movie ID

        Returns:
            Movie: The found movie, or None
        """
        return self.movie_repository.find_movie_by_id(movie_id)

    def get_movie_by_tmdb_id(self, tmdb_id: int) -> Movie:
        """
        Find a movie by its TMDB ID.

        Args:
            tmdb_id: The TMDB movie ID

        Returns:
            Movie: The found movie, or None
        """
        return self.movie_repository.find_movie_by_tmdb_id(tmdb_id)

    def find_or_create_movie(self, tmdb_id: int) -> Movie:
        """
        Find a movie by TMDB ID, or create it if it doesn't exist.

        This method:
        1. Checks if the movie exists in our database
        2. If not, fetches movie data from TMDB API
        3. Creates the movie in our database
        4. Returns the movie

        Args:
            tmdb_id: The TMDB movie ID

        Returns:
            Movie: The found or created movie

        Raises:
            Exception: If TMDB API request fails or movie not found on TMDB
        """
        # Check if movie already exists
        movie = self.movie_repository.find_movie_by_tmdb_id(tmdb_id)

        if movie:
            return movie

        # Movie doesn't exist, fetch from TMDB
        tmdb_data = self.tmdb_service.get_movie_details(tmdb_id)

        # Create movie from TMDB data
        movie = self.movie_repository.create_from_tmdb_data(tmdb_data)

        return movie
