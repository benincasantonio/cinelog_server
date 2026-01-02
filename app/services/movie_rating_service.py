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
        self, user_id: str, tmdbId: str, rating: int, comment: str
    ):
        """
        Create or update a movie rating for a specific user and movie.
        """

        movie = self.movie_service.find_or_create_movie(tmdb_id=tmdbId)

        movie_rating = self.movie_rating_repository.create_update_movie_rating(
            user_id, movie_id=movie.id, rating=rating, comment=comment
        )

        return MovieRatingResponse(
            id=str(movie_rating.id),
            userId=str(movie_rating.userId),
            movieId=str(movie_rating.movieId),
            tmdbId=tmdbId,
            rating=movie_rating.rating,
            comment=movie_rating.review,
            createdAt=movie_rating.createdAt,
            updatedAt=movie_rating.updatedAt,
        )

    def get_movie_rating(self, user_id: str, movie_id: str):
        """
        Get a movie rating for a specific user and movie.
        """

        return self.movie_rating_repository.find_movie_rating_by_user_and_movie(
            user_id, movie_id=movie_id
        )
