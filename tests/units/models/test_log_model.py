from datetime import datetime, timezone

import pytest
from bson import ObjectId

from app.models.log import Log


@pytest.mark.asyncio
async def test_log_creation(beanie_test_db):
    log = Log(
        user_id=ObjectId(),
        movie_id=ObjectId(),
        tmdb_id=10,
        date_watched=datetime(2023, 10, 1, tzinfo=timezone.utc),
        watched_where="cinema",
        viewing_notes="Great movie!",
        poster_path="/path/to/poster.jpg",
    )

    await log.insert()

    assert await Log.find_all().count() == 1
    assert log.id is not None


@pytest.mark.asyncio
async def test_missing_required_fields():
    with pytest.raises(Exception):
        Log(movie_id=ObjectId())


@pytest.mark.asyncio
async def test_required_fields(beanie_test_db):
    log = Log(
        user_id=ObjectId(),
        movie_id=ObjectId(),
        tmdb_id=10,
        date_watched=datetime(2023, 10, 1, tzinfo=timezone.utc),
        watched_where="cinema",
    )

    await log.insert()
    assert await Log.find_all().count() == 1
    assert log.id is not None


@pytest.mark.asyncio
async def test_wrong_watched_where():
    with pytest.raises(Exception):
        Log(
            user_id=ObjectId(),
            movie_id=ObjectId(),
            tmdb_id=10,
            date_watched=datetime(2023, 10, 1, tzinfo=timezone.utc),
            watched_where="unknown",
        )
