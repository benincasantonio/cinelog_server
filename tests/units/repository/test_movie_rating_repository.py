from bson import ObjectId
import pytest

from app.models.movie_rating import MovieRating
from app.repository.movie_rating_repository import MovieRatingRepository


@pytest.mark.asyncio
async def test_find_movie_rating_by_user_and_movie(beanie_test_db):
    repo = MovieRatingRepository()
    user_id = str(ObjectId())
    movie_id = str(ObjectId())

    await repo.create_update_movie_rating(
        user_id=user_id,
        movie_id=movie_id,
        rating=8,
        comment="Great movie!",
        tmdb_id=550,
    )

    result = await repo.find_movie_rating_by_user_and_movie(user_id, movie_id)

    assert result is not None
    assert result.rating == 8


@pytest.mark.asyncio
async def test_find_movie_rating_by_user_and_movie_not_found(beanie_test_db):
    repo = MovieRatingRepository()
    result = await repo.find_movie_rating_by_user_and_movie(
        str(ObjectId()), str(ObjectId())
    )
    assert result is None


@pytest.mark.asyncio
async def test_find_movie_rating_by_user_and_movie_invalid_object_ids(beanie_test_db):
    repo = MovieRatingRepository()
    result = await repo.find_movie_rating_by_user_and_movie(
        "invalid-user-id", "invalid-movie-id"
    )
    assert result is None


@pytest.mark.asyncio
async def test_find_movie_rating_by_user_and_tmdb(beanie_test_db):
    repo = MovieRatingRepository()
    user_id = str(ObjectId())
    movie_id = str(ObjectId())
    await repo.create_update_movie_rating(
        user_id=user_id,
        movie_id=movie_id,
        rating=7,
        comment="Nice",
        tmdb_id=600,
    )

    result = await repo.find_movie_rating_by_user_and_tmdb(user_id, 600)
    assert result is not None
    assert result.tmdb_id == 600


@pytest.mark.asyncio
async def test_find_movie_rating_by_user_and_tmdb_invalid_object_id(beanie_test_db):
    repo = MovieRatingRepository()
    result = await repo.find_movie_rating_by_user_and_tmdb("invalid-user-id", 600)
    assert result is None


@pytest.mark.asyncio
async def test_create_movie_rating_new(beanie_test_db):
    repo = MovieRatingRepository()
    result = await repo.create_update_movie_rating(
        user_id=str(ObjectId()),
        movie_id=str(ObjectId()),
        rating=8,
        comment="Great movie!",
        tmdb_id=550,
    )

    assert result is not None
    assert result.rating == 8


@pytest.mark.asyncio
async def test_update_movie_rating_existing(beanie_test_db):
    repo = MovieRatingRepository()
    user_id = str(ObjectId())
    movie_id = str(ObjectId())
    await repo.create_update_movie_rating(
        user_id=user_id,
        movie_id=movie_id,
        rating=8,
        comment="Great movie!",
        tmdb_id=550,
    )

    result = await repo.create_update_movie_rating(
        user_id=user_id,
        movie_id=movie_id,
        rating=9,
        comment="Even better on rewatch!",
        tmdb_id=550,
    )

    assert result.rating == 9
    assert result.review == "Even better on rewatch!"


@pytest.mark.asyncio
async def test_find_movie_rating_filters_soft_deleted(beanie_test_db):
    repo = MovieRatingRepository()
    user_id = str(ObjectId())
    movie_id = str(ObjectId())
    rating = await repo.create_update_movie_rating(
        user_id=user_id,
        movie_id=movie_id,
        rating=8,
        comment="Great movie!",
        tmdb_id=777,
    )
    rating.deleted = True
    await rating.save()

    assert await repo.find_movie_rating_by_user_and_movie(user_id, movie_id) is None
    assert await repo.find_movie_rating_by_user_and_tmdb(user_id, 777) is None
    raw_rating = await MovieRating.get(rating.id)
    assert raw_rating is not None
    assert raw_rating.deleted is True
