"""Unit tests for ``UserRepository``."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base_model import Base
from app.models.user_model import User
from app.repository.user_repository import UserRepository
from app.schemas.user_schemas import UserCreateRequest


def _async_url(pg, dbname: str) -> str:
    return f"postgresql+asyncpg://{pg.user}:{pg.password}@{pg.host}:{pg.port}/{dbname}"


@pytest_asyncio.fixture
async def pg_engine(postgresql_proc):
    """Create a fresh database per test and return an async SQLAlchemy engine."""
    dbname = f"cinelog_user_test_{uuid4().hex[:8]}"

    with DatabaseJanitor(
        user=postgresql_proc.user,
        host=postgresql_proc.host,
        port=postgresql_proc.port,
        dbname=dbname,
        version=postgresql_proc.version,
        password=postgresql_proc.password,
    ):
        engine = create_async_engine(_async_url(postgresql_proc, dbname))
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            await connection.run_sync(Base.metadata.create_all)

        try:
            yield engine
        finally:
            await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(pg_engine):
    return async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def repository(session_factory) -> UserRepository:
    @asynccontextmanager
    async def _provider():
        async with session_factory() as session:
            yield session

    return UserRepository(session_provider=_provider)


@pytest_asyncio.fixture
async def seed_session(session_factory):
    async with session_factory() as session:
        yield session


def _user_request(
    *,
    first_name: str = "John",
    last_name: str = "Doe",
    email: str = "john@example.com",
    handle: str = "johndoe",
    bio: str | None = None,
    date_of_birth: date = date(1990, 1, 1),
    password_hash: str | None = "$2b$12$hashed",
    profile_visibility: str = "private",
) -> UserCreateRequest:
    return UserCreateRequest(
        first_name=first_name,
        last_name=last_name,
        email=email,
        handle=handle,
        bio=bio,
        date_of_birth=date_of_birth,
        password_hash=password_hash,
        profile_visibility=profile_visibility,
    )


async def _add(seed_session: AsyncSession, *users: User) -> None:
    seed_session.add_all(users)
    await seed_session.commit()
    for user in users:
        await seed_session.refresh(user)


@pytest.mark.asyncio
async def test_create_user_persists_row(repository: UserRepository, seed_session: AsyncSession):
    user = await repository.create_user(_user_request())

    assert user.id is not None
    assert user.email == "john@example.com"
    assert user.handle == "johndoe"
    assert user.deleted is False

    persisted = await seed_session.get(User, user.id)
    assert persisted is not None
    assert persisted.first_name == "John"


@pytest.mark.asyncio
async def test_find_user_by_email_is_case_insensitive(repository: UserRepository):
    await repository.create_user(_user_request(email="User@Example.com", handle="mixedcase"))

    found = await repository.find_user_by_email("user@example.com")

    assert found is not None
    assert found.handle == "mixedcase"


@pytest.mark.asyncio
async def test_email_uniqueness_is_case_insensitive(repository: UserRepository):
    await repository.create_user(_user_request(email="User@Example.com", handle="firsthandle"))

    with pytest.raises(IntegrityError):
        await repository.create_user(_user_request(email="user@example.com", handle="secondhandle"))


@pytest.mark.asyncio
async def test_handle_uniqueness_is_case_insensitive(repository: UserRepository):
    await repository.create_user(_user_request(email="first-handle@example.com", handle="Antonio"))

    with pytest.raises(IntegrityError):
        await repository.create_user(_user_request(email="second-handle@example.com", handle="antonio"))


@pytest.mark.asyncio
async def test_find_user_by_handle_returns_active_row(repository: UserRepository):
    created = await repository.create_user(_user_request(handle="janedoe", email="jane@example.com"))

    found = await repository.find_user_by_handle("JANEDOE")

    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_find_user_by_email_or_handle_matches_both_paths(repository: UserRepository):
    created = await repository.create_user(_user_request(email="lookup@example.com", handle="LookupHandle"))

    found_by_email = await repository.find_user_by_email_or_handle("LOOKUP@example.com")
    found_by_handle = await repository.find_user_by_email_or_handle("lookuphandle")

    assert found_by_email is not None
    assert found_by_handle is not None
    assert found_by_email.id == created.id
    assert found_by_handle.id == created.id


@pytest.mark.asyncio
async def test_find_user_by_id_excludes_deleted_and_unknown(repository: UserRepository, seed_session: AsyncSession):
    active = User(
        email="active@example.com",
        handle="active",
        first_name="Active",
        last_name="User",
        date_of_birth=date(1990, 1, 1),
    )
    deleted = User(
        email="deleted@example.com",
        handle="deleted",
        first_name="Deleted",
        last_name="User",
        date_of_birth=date(1990, 1, 1),
        deleted=True,
        deleted_at=datetime.now(UTC),
    )
    await _add(seed_session, active, deleted)

    assert (await repository.find_user_by_id(active.id)) is not None
    assert (await repository.find_user_by_id(deleted.id)) is None
    assert (await repository.find_user_by_id(uuid4())) is None


@pytest.mark.asyncio
async def test_delete_user_soft_deletes_row(repository: UserRepository, seed_session: AsyncSession):
    user = await repository.create_user(_user_request(email="softdelete@example.com", handle="softdelete"))

    deleted = await repository.delete_user(user.id)

    assert deleted is True
    assert await repository.find_user_by_id(user.id) is None

    persisted = await seed_session.get(User, user.id)
    assert persisted is not None
    assert persisted.deleted is True
    assert persisted.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_user_returns_false_for_unknown_id(repository: UserRepository):
    assert await repository.delete_user(uuid4()) is False


@pytest.mark.asyncio
async def test_delete_user_oblivion_overwrites_sensitive_fields(repository: UserRepository, seed_session: AsyncSession):
    user = await repository.create_user(
        _user_request(
            email="obliterate@example.com",
            handle="obliterate",
            bio="Sensitive bio",
        )
    )
    user = await repository.set_reset_password_code(user, "RESET", datetime.now(UTC))

    deleted = await repository.delete_user_oblivion(user.id)

    assert deleted is True
    persisted = await seed_session.get(User, user.id)
    assert persisted is not None
    assert persisted.first_name == "Deleted"
    assert persisted.last_name == "User"
    assert persisted.email == f"deleted_{user.id}@deleted.local"
    assert persisted.handle == f"deleted_{user.id}"
    assert persisted.bio is None
    assert persisted.password_hash is None
    assert persisted.reset_password_code is None
    assert persisted.reset_password_expires is None
    assert persisted.date_of_birth is None
    assert persisted.deleted is True


@pytest.mark.asyncio
async def test_update_password_changes_hash(repository: UserRepository, seed_session: AsyncSession):
    user = await repository.create_user(_user_request(email="password@example.com", handle="passwordhandle"))

    updated = await repository.update_password(user, "$2b$12$new_hashed")

    assert updated.password_hash == "$2b$12$new_hashed"
    persisted = await seed_session.get(User, user.id)
    assert persisted is not None
    assert persisted.password_hash == "$2b$12$new_hashed"


@pytest.mark.asyncio
async def test_set_reset_password_code_updates_fields(repository: UserRepository):
    user = await repository.create_user(_user_request(email="reset@example.com", handle="resethandle"))
    expires_at = datetime.now(UTC)

    updated = await repository.set_reset_password_code(user, "ABC123", expires_at)

    assert updated.reset_password_code == "ABC123"
    assert updated.reset_password_expires == expires_at


@pytest.mark.asyncio
async def test_clear_reset_password_code_nulls_fields(repository: UserRepository):
    user = await repository.create_user(_user_request(email="clear@example.com", handle="clearhandle"))
    user = await repository.set_reset_password_code(user, "ABC123", datetime.now(UTC))

    updated = await repository.clear_reset_password_code(user)

    assert updated.reset_password_code is None
    assert updated.reset_password_expires is None


@pytest.mark.asyncio
async def test_update_user_profile_only_changes_whitelisted_fields(
    repository: UserRepository, seed_session: AsyncSession
):
    user = await repository.create_user(
        _user_request(
            email="profile@example.com",
            handle="profilehandle",
            bio="Old bio",
        )
    )

    updated = await repository.update_user_profile(
        user.id,
        {
            "first_name": "Jane",
            "last_name": "Smith",
            "bio": "New bio",
            "profile_visibility": "public",
            "date_of_birth": date(1991, 2, 3),
            "email": "ignored@example.com",
        },
    )

    assert updated is not None
    assert updated.first_name == "Jane"
    assert updated.last_name == "Smith"
    assert updated.bio == "New bio"
    assert updated.profile_visibility == "public"
    assert updated.date_of_birth == date(1991, 2, 3)

    persisted = await seed_session.get(User, user.id)
    assert persisted is not None
    assert persisted.email == "profile@example.com"


@pytest.mark.asyncio
async def test_profile_visibility_check_constraint_rejects_invalid_value(seed_session: AsyncSession):
    invalid_user = User(
        email="invalid-visibility@example.com",
        handle="invalidvisibility",
        first_name="Invalid",
        last_name="Visibility",
        date_of_birth=date(1990, 1, 1),
        profile_visibility="hidden",
    )

    seed_session.add(invalid_user)

    with pytest.raises(IntegrityError):
        await seed_session.commit()
