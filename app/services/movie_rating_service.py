from app.repository.movie_rating_repository import MovieRatingRepository
from app.schemas.movie_rating_schemas import MovieRatingResponse
from app.services.movie_service import MovieService


class MovieRatingService:

    def __init__(
        self,
        movie_rating_repository: MovieRatingRepository,
        movie_service: MovieService,
    ):
        self.movie_rating_repository = movie_rating_repository
        self.movie_service = movie_service

    def create_update_movie_rating(
        self, user_id: str, tmdb_id: int, rating: int, comment: str | None = None
    ):
        """
        Create or update a movie rating for a specific user and movie.
        """

        movie = self.movie_service.find_or_create_movie(tmdb_id=tmdb_id)

        movie_rating = self.movie_rating_repository.create_update_movie_rating(
            user_id, movie_id=movie.id, rating=rating, comment=comment, tmdb_id=tmdb_id
        )

        return self._get_movie_rating_response(movie_rating)

    def get_movie_rating(self, user_id: str, movie_id: str):
        """
        Get a movie rating for a specific user and movie.
        """

        movie_rating = self.movie_rating_repository.find_movie_rating_by_user_and_movie(
            user_id, movie_id=movie_id
        )

        if not movie_rating:
            return None

        return MovieRatingResponse(
            id=str(movie_rating.id),
            user_id=str(movie_rating.user_id),
            movie_id=str(movie_rating.movie_id),
            tmdb_id=str(movie_rating.tmdb_id),
            rating=movie_rating.rating,
            comment=movie_rating.review,
            created_at=movie_rating.created_at,
            updated_at=movie_rating.updated_at,
        )

    def get_movie_ratings_by_tmdb_id(self, user_id: str, tmdb_id: int):
        """
        Get all movie ratings for a specific TMDB ID.
        """

        movie_rating = self.movie_rating_repository.find_movie_rating_by_user_and_tmdb(
            user_id, tmdb_id=tmdb_id
        )

        if not movie_rating:
            return None

        return self._get_movie_rating_response(movie_rating)

    def _get_movie_rating_response(self, movie_rating) -> MovieRatingResponse:
        return MovieRatingResponse(
            id=str(movie_rating.id),
            user_id=str(movie_rating.user_id),
            movie_id=str(movie_rating.movie_id),
            tmdb_id=str(movie_rating.tmdb_id),
            rating=movie_rating.rating,
            comment=movie_rating.review,
            created_at=movie_rating.created_at,
            updated_at=movie_rating.updated_at,
        )
