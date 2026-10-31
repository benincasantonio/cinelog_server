from uuid import UUID

from app.repository.movie_rating_repository_protocol import MovieRatingRepositoryProtocol
from app.schemas.movie_rating_schemas import MovieRatingResponse
from app.services.log_list_cache_service import LogListCacheService
from app.services.movie_service import MovieService
from app.services.stats_cache_service import StatsCacheService
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


class MovieRatingService:
    def __init__(
        self,
        movie_rating_repository: MovieRatingRepositoryProtocol,
        movie_service: MovieService,
        log_list_cache_service: LogListCacheService | None = None,
        stats_cache_service: StatsCacheService | None = None,
    ):
        self.movie_rating_repository = movie_rating_repository
        self.movie_service = movie_service
        self.log_list_cache_service = log_list_cache_service or LogListCacheService()
        self.stats_cache_service = stats_cache_service or StatsCacheService()

    async def create_update_movie_rating(
        self,
        user_id: UUID,
        movie_id: UUID,
        rating: int,
        comment: str | None = None,
    ) -> MovieRatingResponse:
        """
        Create or update a movie rating for a specific user and movie.
        """

        movie = await self.movie_service.get_active_movie(movie_id)

        movie_rating = await self.movie_rating_repository.create_update_movie_rating(
            user_id=user_id,
            movie_id=movie.id,
            rating=rating,
            comment=comment,
        )

        await self.log_list_cache_service.invalidate_user(user_id)
        await self.stats_cache_service.invalidate_user_stats(user_id)

        return self._get_movie_rating_response(movie_rating)

    async def get_movie_rating(self, movie_id: UUID, user_id: UUID) -> MovieRatingResponse | None:
        """
        Get the caller's rating for an active movie. Returns None if no rating exists.
        """

        movie = await self.movie_service.get_active_movie(movie_id)

        movie_rating = await self.movie_rating_repository.find_movie_rating_by_user_and_movie(
            user_id=user_id, movie_id=movie.id
        )

        if not movie_rating:
            return None

        return self._get_movie_rating_response(movie_rating)

    def _get_movie_rating_response(self, movie_rating) -> MovieRatingResponse:
        if movie_rating.rating is None:
            raise AppException(ErrorCodes.MOVIE_RATING_VALUE_REQUIRED)

        return MovieRatingResponse(
            id=str(movie_rating.id),
            user_id=str(movie_rating.user_id),
            movie_id=str(movie_rating.movie_id),
            rating=movie_rating.rating,
            comment=movie_rating.review,
            created_at=movie_rating.created_at,
            updated_at=movie_rating.updated_at,
        )
