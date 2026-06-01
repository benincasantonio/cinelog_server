"""Migrate movie ratings data from MongoDB to PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie_model import PostgresMovie
from app.models.movie_rating_model import PostgresMovieRating
from app.models.user_model import PostgresUser
from app.utils.id_utils import mongo_id_to_uuid

BATCH_SIZE = 100


class BatchOutcome(NamedTuple):
    inserted: int
    skipped: int
    warnings: int


def _normalize_movie_rating_doc(mongo_rating: dict) -> dict:
    mongo_user_id = mongo_rating.get("userId")
    mongo_movie_id = mongo_rating.get("movieId")

    return {
        "id": mongo_id_to_uuid(str(mongo_rating["_id"])),
        "user_id": mongo_id_to_uuid(str(mongo_user_id)) if mongo_user_id is not None else None,
        "movie_id": mongo_id_to_uuid(str(mongo_movie_id)) if mongo_movie_id is not None else None,
        "tmdb_id": mongo_rating.get("tmdbId"),
        "rating": mongo_rating.get("rating"),
        "review": mongo_rating.get("review"),
        "deleted": bool(mongo_rating.get("deleted", False)),
        "deleted_at": mongo_rating.get("deletedAt"),
        "created_at": mongo_rating.get("createdAt") or datetime.now(UTC),
        "updated_at": mongo_rating.get("updatedAt") or datetime.now(UTC),
    }


def _warn_missing_reference(values: dict, reason: str) -> None:
    print(f"[movie-ratings-migration:warn] rating_id={values['id']} {reason}")


async def _validate_batch_foreign_keys(
    pg_session: AsyncSession,
    batch: list[dict],
) -> tuple[list[dict], int]:
    """Filter out rows with missing required values or unresolved foreign keys."""

    prelim_valid: list[dict] = []
    warnings = 0

    for values in batch:
        if values["user_id"] is None or values["movie_id"] is None or values["tmdb_id"] is None:
            _warn_missing_reference(values, "missing required user_id, movie_id, or tmdb_id")
            warnings += 1
            continue
        prelim_valid.append(values)

    if not prelim_valid:
        return [], warnings

    user_ids = {values["user_id"] for values in prelim_valid}
    movie_ids = {values["movie_id"] for values in prelim_valid}

    user_result = await pg_session.execute(select(PostgresUser.id).where(PostgresUser.id.in_(user_ids)))
    movie_result = await pg_session.execute(select(PostgresMovie.id).where(PostgresMovie.id.in_(movie_ids)))

    existing_user_ids = set(user_result.scalars().all())
    existing_movie_ids = set(movie_result.scalars().all())

    valid: list[dict] = []
    for values in prelim_valid:
        missing_parts: list[str] = []
        if values["user_id"] not in existing_user_ids:
            missing_parts.append("user FK missing")
        if values["movie_id"] not in existing_movie_ids:
            missing_parts.append("movie FK missing")

        if missing_parts:
            _warn_missing_reference(values, ", ".join(missing_parts))
            warnings += 1
            continue

        valid.append(values)

    return valid, warnings


async def _count_dry_run_insertable_ratings(
    pg_session: AsyncSession,
    batch: list[dict],
    projected_pairs: set[tuple[UUID, int]],
) -> int:
    """Count how many valid rows a dry-run batch would insert after conflicts."""

    batch_user_ids = {values["user_id"] for values in batch}
    batch_tmdb_ids = {values["tmdb_id"] for values in batch}
    statement = select(PostgresMovieRating.user_id, PostgresMovieRating.tmdb_id).where(
        PostgresMovieRating.user_id.in_(batch_user_ids),
        PostgresMovieRating.tmdb_id.in_(batch_tmdb_ids),
    )
    result = await pg_session.execute(statement)

    occupied_pairs = set(projected_pairs)
    occupied_pairs.update((user_id, tmdb_id) for user_id, tmdb_id in result.all())

    insertable_pairs: set[tuple[UUID, int]] = set()
    for values in batch:
        pair = (values["user_id"], values["tmdb_id"])
        if pair in occupied_pairs or pair in insertable_pairs:
            continue
        insertable_pairs.add(pair)

    projected_pairs.update(insertable_pairs)
    return len(insertable_pairs)


async def _flush_batch(
    pg_session: AsyncSession,
    batch: list[dict],
    *,
    dry_run: bool,
    projected_pairs: set[tuple[UUID, int]] | None = None,
) -> BatchOutcome:
    """Insert a batch and return inserted/skipped/warning counts."""

    if not batch:
        return BatchOutcome(inserted=0, skipped=0, warnings=0)

    valid_batch, warnings = await _validate_batch_foreign_keys(pg_session, batch)
    if not valid_batch:
        return BatchOutcome(inserted=0, skipped=len(batch), warnings=warnings)

    if dry_run:
        inserted = await _count_dry_run_insertable_ratings(
            pg_session,
            valid_batch,
            projected_pairs if projected_pairs is not None else set(),
        )
        return BatchOutcome(inserted=inserted, skipped=len(batch) - inserted, warnings=warnings)

    statement = (
        insert(PostgresMovieRating)
        .values(valid_batch)
        .on_conflict_do_nothing(index_elements=[PostgresMovieRating.user_id, PostgresMovieRating.tmdb_id])
        .returning(PostgresMovieRating.id)
    )
    result = await pg_session.execute(statement)
    inserted = len(result.scalars().all())
    return BatchOutcome(inserted=inserted, skipped=len(batch) - inserted, warnings=warnings)


async def up(mongo_db, pg_session: AsyncSession, dry_run: bool = False) -> None:
    """Migrate active movie ratings from MongoDB into PostgreSQL in batches."""

    cursor = mongo_db.movie_ratings.find({"deleted": {"$ne": True}}, batch_size=BATCH_SIZE)

    total = 0
    inserted = 0
    skipped = 0
    warnings = 0
    batch: list[dict] = []
    projected_pairs: set[tuple[UUID, int]] = set()

    for mongo_rating in cursor:
        total += 1
        batch.append(_normalize_movie_rating_doc(mongo_rating))

        if len(batch) >= BATCH_SIZE:
            outcome = await _flush_batch(
                pg_session,
                batch,
                dry_run=dry_run,
                projected_pairs=projected_pairs,
            )
            inserted += outcome.inserted
            skipped += outcome.skipped
            warnings += outcome.warnings
            batch = []

    if batch:
        outcome = await _flush_batch(
            pg_session,
            batch,
            dry_run=dry_run,
            projected_pairs=projected_pairs,
        )
        inserted += outcome.inserted
        skipped += outcome.skipped
        warnings += outcome.warnings

    if not dry_run:
        await pg_session.commit()

    print(
        "[movie-ratings-migration] "
        f"total={total} inserted={inserted} skipped={skipped} warnings={warnings} dry_run={dry_run}"
    )


async def down(mongo_db, pg_session: AsyncSession) -> None:
    """Rollback movie-rating migration by deleting only rows derived from Mongo."""

    cursor = mongo_db.movie_ratings.find({}, batch_size=BATCH_SIZE)
    derived_ids = [mongo_id_to_uuid(str(doc["_id"])) for doc in cursor]

    deleted_count = 0
    if derived_ids:
        result = await pg_session.execute(
            delete(PostgresMovieRating).where(PostgresMovieRating.id.in_(derived_ids)).returning(PostgresMovieRating.id)
        )
        deleted_count = len(result.scalars().all())
        await pg_session.commit()

    print(f"[movie-ratings-migration:down] derived_ids={len(derived_ids)} deleted={deleted_count}")
