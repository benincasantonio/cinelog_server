"""Migrate users data from MongoDB to PostgreSQL."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_model import PostgresUser
from app.utils.id_utils import mongo_id_to_uuid

BATCH_SIZE = 100


def _parse_date_of_birth(value: str | date | datetime | None) -> date | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if not isinstance(value, str) or not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None


def _normalize_user_doc(mongo_user: dict) -> dict:
    return {
        "id": mongo_id_to_uuid(str(mongo_user["_id"])),
        "email": mongo_user.get("email") or "",
        "handle": mongo_user.get("handle") or "",
        "first_name": mongo_user.get("firstName") or "",
        "last_name": mongo_user.get("lastName") or "",
        "bio": mongo_user.get("bio"),
        "profile_visibility": mongo_user.get("profileVisibility") or "private",
        "date_of_birth": _parse_date_of_birth(mongo_user.get("dateOfBirth")),
        "password_hash": mongo_user.get("passwordHash"),
        "reset_password_code": mongo_user.get("resetPasswordCode"),
        "reset_password_expires": mongo_user.get("resetPasswordExpires"),
        "deleted": bool(mongo_user.get("deleted", False)),
        "deleted_at": mongo_user.get("deletedAt"),
        "created_at": mongo_user.get("createdAt") or datetime.now(UTC),
        "updated_at": mongo_user.get("updatedAt") or datetime.now(UTC),
    }


async def _count_dry_run_insertable_users(
    pg_session: AsyncSession,
    batch: list[dict],
    projected_lower_emails: set[str],
    projected_handles: set[str],
) -> int:
    """Count dry-run inserts after case-insensitive email and handle conflicts."""

    batch_lower_emails = {values["email"].lower() for values in batch}
    batch_handles = {values["handle"] for values in batch}
    statement = select(func.lower(PostgresUser.email), PostgresUser.handle).where(
        or_(
            func.lower(PostgresUser.email).in_(batch_lower_emails),
            PostgresUser.handle.in_(batch_handles),
        )
    )
    result = await pg_session.execute(statement)

    occupied_lower_emails = set(projected_lower_emails)
    occupied_handles = set(projected_handles)

    for lower_email, handle in result.all():
        occupied_lower_emails.add(str(lower_email))
        occupied_handles.add(str(handle))

    insertable_lower_emails: set[str] = set()
    insertable_handles: set[str] = set()

    for values in batch:
        lower_email = values["email"].lower()
        handle = values["handle"]
        if (
            lower_email in occupied_lower_emails
            or handle in occupied_handles
            or lower_email in insertable_lower_emails
            or handle in insertable_handles
        ):
            continue

        insertable_lower_emails.add(lower_email)
        insertable_handles.add(handle)

    projected_lower_emails.update(insertable_lower_emails)
    projected_handles.update(insertable_handles)
    return len(insertable_lower_emails)


async def _flush_batch(
    pg_session: AsyncSession,
    batch: list[dict],
    *,
    dry_run: bool,
    projected_lower_emails: set[str] | None = None,
    projected_handles: set[str] | None = None,
) -> int:
    """Insert a batch and return how many rows were actually persisted."""

    if not batch:
        return 0

    if dry_run:
        return await _count_dry_run_insertable_users(
            pg_session,
            batch,
            projected_lower_emails if projected_lower_emails is not None else set(),
            projected_handles if projected_handles is not None else set(),
        )

    statement = insert(PostgresUser).values(batch).on_conflict_do_nothing().returning(PostgresUser.id)
    result = await pg_session.execute(statement)
    return len(result.scalars().all())


async def up(mongo_db, pg_session: AsyncSession, dry_run: bool = False) -> None:
    """Migrate active users from MongoDB into PostgreSQL in batches."""

    cursor = mongo_db.users.find({"deleted": {"$ne": True}}, batch_size=BATCH_SIZE)

    total = 0
    inserted = 0
    skipped = 0
    batch: list[dict] = []
    projected_lower_emails: set[str] = set()
    projected_handles: set[str] = set()

    for mongo_user in cursor:
        total += 1
        values = _normalize_user_doc(mongo_user)
        if not values["email"] or not values["handle"] or not values["first_name"] or not values["last_name"]:
            skipped += 1
            continue

        batch.append(values)

        if len(batch) >= BATCH_SIZE:
            inserted_in_batch = await _flush_batch(
                pg_session,
                batch,
                dry_run=dry_run,
                projected_lower_emails=projected_lower_emails,
                projected_handles=projected_handles,
            )
            inserted += inserted_in_batch
            skipped += len(batch) - inserted_in_batch
            batch = []

    if batch:
        inserted_in_batch = await _flush_batch(
            pg_session,
            batch,
            dry_run=dry_run,
            projected_lower_emails=projected_lower_emails,
            projected_handles=projected_handles,
        )
        inserted += inserted_in_batch
        skipped += len(batch) - inserted_in_batch

    if not dry_run:
        await pg_session.commit()

    print(f"[users-migration] total={total} inserted={inserted} skipped={skipped} dry_run={dry_run}")


async def down(mongo_db, pg_session: AsyncSession) -> None:
    """Rollback user migration by deleting only rows derived from current Mongo users."""

    cursor = mongo_db.users.find({}, batch_size=BATCH_SIZE)
    derived_ids = [mongo_id_to_uuid(str(doc["_id"])) for doc in cursor]

    deleted = 0
    if derived_ids:
        result = await pg_session.execute(
            delete(PostgresUser).where(PostgresUser.id.in_(derived_ids)).returning(PostgresUser.id)
        )
        deleted = len(result.scalars().all())
        await pg_session.commit()

    print(f"[users-migration:down] derived_ids={len(derived_ids)} deleted={deleted}")
