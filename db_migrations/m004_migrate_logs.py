"""Migrate logs data from MongoDB to PostgreSQL."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log_model import PostgresLog
from app.models.movie_model import PostgresMovie
from app.models.user_model import PostgresUser
from app.types import WATCHED_WHERE_CHOICES
from app.utils.datetime_utils import to_utc_datetime
from app.utils.id_utils import mongo_id_to_uuid

BATCH_SIZE = 100


class BatchOutcome(NamedTuple):
    inserted: int
    skipped: int
    warnings: int


def _parse_date_watched(value: str | date | datetime | None) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return to_utc_datetime(value)

    if isinstance(value, date):
        return to_utc_datetime(value)

    if not isinstance(value, str) or not value:
        return None

    try:
        if "T" in value or " " in value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return to_utc_datetime(parsed)
        return to_utc_datetime(date.fromisoformat(value))
    except ValueError:
        return None


def _normalize_watched_where(value: object) -> str:
    if isinstance(value, str) and value in WATCHED_WHERE_CHOICES:
        return value
    return "other"


def _normalize_log_doc(mongo_log: dict) -> dict:
    mongo_user_id = mongo_log.get("userId")
    mongo_movie_id = mongo_log.get("movieId")

    return {
        "id": mongo_id_to_uuid(str(mongo_log["_id"])),
        "user_id": mongo_id_to_uuid(str(mongo_user_id)) if mongo_user_id is not None else None,
        "movie_id": mongo_id_to_uuid(str(mongo_movie_id)) if mongo_movie_id is not None else None,
        "tmdb_id": mongo_log.get("tmdbId"),
        "date_watched": _parse_date_watched(mongo_log.get("dateWatched")),
        "viewing_notes": mongo_log.get("viewingNotes"),
        "poster_path": mongo_log.get("posterPath"),
        "watched_where": _normalize_watched_where(mongo_log.get("watchedWhere")),
        "deleted": bool(mongo_log.get("deleted", False)),
        "deleted_at": mongo_log.get("deletedAt"),
        "created_at": mongo_log.get("createdAt") or datetime.now(UTC),
        "updated_at": mongo_log.get("updatedAt") or datetime.now(UTC),
    }


def _warn(values: dict, reason: str) -> None:
    print(f"[logs-migration:warn] log_id={values['id']} {reason}")


async def _validate_batch(
    pg_session: AsyncSession,
    batch: list[dict],
) -> tuple[list[dict], int]:
    """Filter out rows missing required values or foreign keys."""

    prelim_valid: list[dict] = []
    warnings = 0

    for values in batch:
        if values["user_id"] is None or values["movie_id"] is None or values["tmdb_id"] is None:
            _warn(values, "missing required user_id, movie_id, or tmdb_id")
            warnings += 1
            continue
        if values["date_watched"] is None:
            _warn(values, "missing or invalid date_watched")
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
            _warn(values, ", ".join(missing_parts))
            warnings += 1
            continue

        valid.append(values)

    return valid, warnings


async def _count_dry_run_insertable_logs(
    pg_session: AsyncSession,
    batch: list[dict],
    projected_ids: set[UUID],
) -> int:
    """Count how many valid rows a dry-run batch would insert after ID conflicts."""

    batch_ids = {values["id"] for values in batch}
    result = await pg_session.execute(select(PostgresLog.id).where(PostgresLog.id.in_(batch_ids)))

    occupied_ids = set(projected_ids)
    occupied_ids.update(result.scalars().all())

    insertable_ids: set[UUID] = set()
    for values in batch:
        log_id = values["id"]
        if log_id in occupied_ids or log_id in insertable_ids:
            continue
        insertable_ids.add(log_id)

    projected_ids.update(insertable_ids)
    return len(insertable_ids)


async def _flush_batch(
    pg_session: AsyncSession,
    batch: list[dict],
    *,
    dry_run: bool,
    projected_ids: set[UUID] | None = None,
) -> BatchOutcome:
    """Insert a batch and return inserted/skipped/warning counts."""

    if not batch:
        return BatchOutcome(inserted=0, skipped=0, warnings=0)

    valid_batch, warnings = await _validate_batch(pg_session, batch)
    if not valid_batch:
        return BatchOutcome(inserted=0, skipped=len(batch), warnings=warnings)

    if dry_run:
        inserted = await _count_dry_run_insertable_logs(
            pg_session,
            valid_batch,
            projected_ids if projected_ids is not None else set(),
        )
        return BatchOutcome(inserted=inserted, skipped=len(batch) - inserted, warnings=warnings)

    statement = (
        insert(PostgresLog)
        .values(valid_batch)
        .on_conflict_do_nothing(index_elements=[PostgresLog.id])
        .returning(PostgresLog.id)
    )
    result = await pg_session.execute(statement)
    inserted = len(result.scalars().all())
    return BatchOutcome(inserted=inserted, skipped=len(batch) - inserted, warnings=warnings)


async def up(mongo_db, pg_session: AsyncSession, dry_run: bool = False) -> None:
    """Migrate active logs from MongoDB into PostgreSQL in batches."""

    cursor = mongo_db.logs.find({"deleted": {"$ne": True}}, batch_size=BATCH_SIZE)

    total = 0
    inserted = 0
    skipped = 0
    warnings = 0
    batch: list[dict] = []
    projected_ids: set[UUID] = set()

    for mongo_log in cursor:
        total += 1
        batch.append(_normalize_log_doc(mongo_log))

        if len(batch) >= BATCH_SIZE:
            outcome = await _flush_batch(
                pg_session,
                batch,
                dry_run=dry_run,
                projected_ids=projected_ids,
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
            projected_ids=projected_ids,
        )
        inserted += outcome.inserted
        skipped += outcome.skipped
        warnings += outcome.warnings

    if not dry_run:
        await pg_session.commit()

    print(f"[logs-migration] total={total} inserted={inserted} skipped={skipped} warnings={warnings} dry_run={dry_run}")


async def down(mongo_db, pg_session: AsyncSession) -> None:
    """Rollback log migration by deleting only rows derived from Mongo."""

    cursor = mongo_db.logs.find({}, batch_size=BATCH_SIZE)
    derived_ids = [mongo_id_to_uuid(str(doc["_id"])) for doc in cursor]

    deleted_count = 0
    if derived_ids:
        result = await pg_session.execute(
            delete(PostgresLog).where(PostgresLog.id.in_(derived_ids)).returning(PostgresLog.id)
        )
        deleted_count = len(result.scalars().all())
        await pg_session.commit()

    print(f"[logs-migration:down] derived_ids={len(derived_ids)} deleted={deleted_count}")
