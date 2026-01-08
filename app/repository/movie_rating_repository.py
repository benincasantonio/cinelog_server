from app.models.movie_rating import MovieRating


class MovieRatingRepository:

    @staticmethod
    def find_movie_rating_by_user_and_movie(user_id: str, movie_id: str) -> MovieRating:
        """
        Find a movie rating by user ID and movie ID.
        """
        return MovieRating.objects(user_id=user_id, movie_id=movie_id).first()

    def find_movie_rating_by_user_and_tmdb(
        self, user_id: str, tmdb_id: str
    ) -> MovieRating:
        """
        Find a movie rating by user ID and TMDB ID.
        """
        return MovieRating.objects(user_id=user_id, tmdb_id=tmdb_id).first()

    @staticmethod
    def create_update_movie_rating(
        user_id: str, movie_id: str, rating: int, comment: str, tmdb_id: int
    ) -> MovieRating:
        """
        Create or update a movie rating for a specific user and movie.
        If a rating already exists for the user and movie, it will be updated.
        """
        existing_rating = MovieRatingRepository.find_movie_rating_by_user_and_movie(
            user_id, movie_id
        )

        if existing_rating:
            existing_rating.rating = rating
            existing_rating.review = comment
            existing_rating.save()
            return existing_rating
        else:
            new_rating = MovieRating(
                user_id=user_id,
                movie_id=movie_id,
                rating=rating,
                review=comment,
                tmdb_id=tmdb_id,
            )
            new_rating.save()
            return new_rating
