from app.models.movie_rating import MovieRating
from app.utils.object_id_utils import to_object_id


class MovieRatingRepository:
    @staticmethod
    async def find_movie_rating_by_user_and_movie(
        user_id: str, movie_id: str
    ) -> MovieRating | None:
        """
        Find a movie rating by user ID and movie ID.
        """
        user_object_id = to_object_id(user_id)
        movie_object_id = to_object_id(movie_id)
        if user_object_id is None or movie_object_id is None:
            return None
        return await MovieRating.find_one(
            MovieRating.active_filter(
                {"userId": user_object_id, "movieId": movie_object_id}
            )
        )

    async def find_movie_rating_by_user_and_tmdb(
        self, user_id: str, tmdb_id: int
    ) -> MovieRating | None:
        """
        Find a movie rating by user ID and TMDB ID.
        """
        user_object_id = to_object_id(user_id)
        if user_object_id is None:
            return None
        return await MovieRating.find_one(
            MovieRating.active_filter(
                {"userId": user_object_id, "tmdbId": tmdb_id}
            )
        )

    @staticmethod
    async def create_update_movie_rating(
        user_id: str, movie_id: str, rating: int, comment: str | None, tmdb_id: int
    ) -> MovieRating:
        """
        Create or update a movie rating for a specific user and movie.
        If a rating already exists for the user and movie, it will be updated.
        """
        existing_rating = (
            await MovieRatingRepository.find_movie_rating_by_user_and_movie(
                user_id, movie_id
            )
        )

        if existing_rating:
            existing_rating.rating = rating
            existing_rating.review = comment
            await existing_rating.save()
            return existing_rating

        user_object_id = to_object_id(user_id)
        movie_object_id = to_object_id(movie_id)
        if user_object_id is None or movie_object_id is None:
            raise ValueError("Invalid user_id or movie_id")

        new_rating = MovieRating(
            user_id=user_object_id,
            movie_id=movie_object_id,
            rating=rating,
            review=comment,
            tmdb_id=tmdb_id,
        )
        await new_rating.insert()
        return new_rating
