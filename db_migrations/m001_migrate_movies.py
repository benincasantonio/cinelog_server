"""Migrate movies data from MongoDB to PostgreSQL."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie_model import PostgresMovie
from app.utils.id_utils import mongo_id_to_uuid

BATCH_SIZE = 100


def _parse_release_date(value: str | date | datetime | None) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.replace(tzinfo=None)

    if isinstance(value, date):
        return datetime(year=value.year, month=value.month, day=value.day)

    if not isinstance(value, str) or not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _normalize_movie_doc(mongo_movie: dict) -> dict:
    return {
        "id": mongo_id_to_uuid(str(mongo_movie["_id"])),
        "tmdb_id": mongo_movie.get("tmdbId"),
        "title": mongo_movie.get("title") or "",
        "release_date": _parse_release_date(mongo_movie.get("releaseDate")),
        "overview": mongo_movie.get("overview"),
        "poster_path": mongo_movie.get("posterPath"),
        "vote_average": mongo_movie.get("voteAverage"),
        "runtime": mongo_movie.get("runtime"),
        "original_language": mongo_movie.get("originalLanguage"),
        "tmdb_payload": mongo_movie.get("tmdbPayload"),
        "tmdb_last_synced_at": mongo_movie.get("tmdbLastSyncedAt"),
        "deleted": bool(mongo_movie.get("deleted", False)),
        "deleted_at": mongo_movie.get("deletedAt"),
        "created_at": mongo_movie.get("createdAt") or datetime.now(UTC),
        "updated_at": mongo_movie.get("updatedAt") or datetime.now(UTC),
    }


async def _count_dry_run_insertable_movies(
    pg_session: AsyncSession,
    batch: list[dict],
    projected_tmdb_ids: set[int],
) -> int:
    """Count how many rows a dry-run batch would insert after uniqueness conflicts."""
    batch_tmdb_ids = {values["tmdb_id"] for values in batch}
    result = await pg_session.execute(select(PostgresMovie.tmdb_id).where(PostgresMovie.tmdb_id.in_(batch_tmdb_ids)))
    occupied_tmdb_ids = projected_tmdb_ids | set(result.scalars().all())
    insertable_tmdb_ids: set[int] = set()

    for values in batch:
        tmdb_id = values["tmdb_id"]
        if tmdb_id in occupied_tmdb_ids or tmdb_id in insertable_tmdb_ids:
            continue
        insertable_tmdb_ids.add(tmdb_id)

    projected_tmdb_ids.update(insertable_tmdb_ids)
    return len(insertable_tmdb_ids)


async def _flush_batch(
    pg_session: AsyncSession,
    batch: list[dict],
    *,
    dry_run: bool,
    projected_tmdb_ids: set[int] | None = None,
) -> int:
    """Insert a batch and return how many rows were actually persisted."""
    if not batch:
        return 0

    if dry_run:
        return await _count_dry_run_insertable_movies(
            pg_session,
            batch,
            projected_tmdb_ids if projected_tmdb_ids is not None else set(),
        )

    statement = (
        insert(PostgresMovie)
        .values(batch)
        .on_conflict_do_nothing(index_elements=[PostgresMovie.tmdb_id])
        .returning(PostgresMovie.tmdb_id)
    )
    result = await pg_session.execute(statement)
    return len(result.scalars().all())


async def up(mongo_db, pg_session: AsyncSession, dry_run: bool = False) -> None:
    """Migrate active movies from MongoDB into PostgreSQL in batches."""

    cursor = mongo_db.movies.find({"deleted": {"$ne": True}}, batch_size=BATCH_SIZE)

    total = 0
    inserted = 0
    skipped = 0
    batch: list[dict] = []
    projected_tmdb_ids: set[int] = set()

    for mongo_movie in cursor:
        total += 1
        values = _normalize_movie_doc(mongo_movie)
        if values["tmdb_id"] is None:
            skipped += 1
            continue

        batch.append(values)

        if len(batch) >= BATCH_SIZE:
            inserted_in_batch = await _flush_batch(
                pg_session,
                batch,
                dry_run=dry_run,
                projected_tmdb_ids=projected_tmdb_ids,
            )
            inserted += inserted_in_batch
            skipped += len(batch) - inserted_in_batch
            batch = []

    if batch:
        inserted_in_batch = await _flush_batch(
            pg_session,
            batch,
            dry_run=dry_run,
            projected_tmdb_ids=projected_tmdb_ids,
        )
        inserted += inserted_in_batch
        skipped += len(batch) - inserted_in_batch

    if not dry_run:
        await pg_session.commit()

    print(f"[movies-migration] total={total} inserted={inserted} skipped={skipped} dry_run={dry_run}")


async def down(mongo_db, pg_session: AsyncSession) -> None:
    """Rollback movie migration by deleting only the PostgreSQL rows derived from Mongo.

    Scoped to UUIDs produced by ``mongo_id_to_uuid`` over the current Mongo
    ``movies`` collection, so any PG rows added outside the migration are
    preserved.
    """

    cursor = mongo_db.movies.find({}, batch_size=BATCH_SIZE)
    derived_ids = [mongo_id_to_uuid(str(doc["_id"])) for doc in cursor]

    deleted = 0
    if derived_ids:
        result = await pg_session.execute(
            delete(PostgresMovie).where(PostgresMovie.id.in_(derived_ids)).returning(PostgresMovie.id)
        )
        deleted = len(result.scalars().all())
        await pg_session.commit()

    print(f"[movies-migration:down] derived_ids={len(derived_ids)} deleted={deleted}")
