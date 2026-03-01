from datetime import date
from datetime import datetime, UTC

import pytest

from app.models.user import User
from app.repository.user_repository import UserRepository
from app.schemas.user_schemas import UserCreateRequest


@pytest.fixture
def user_create_request():
    return UserCreateRequest(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        password_hash="hash",
        handle="johndoe",
        date_of_birth=date(1990, 1, 1),
    )


@pytest.mark.asyncio
async def test_create_user(beanie_test_db, user_create_request):
    repository = UserRepository()
    user = await repository.create_user(user_create_request)

    assert user is not None
    assert user.id is not None
    assert user.first_name == user_create_request.first_name
    assert user.last_name == user_create_request.last_name
    assert user.email == user_create_request.email
    assert await User.find_all().count() == 1


@pytest.mark.asyncio
async def test_cannot_create_user_with_same_email(beanie_test_db):
    repository = UserRepository()
    user_request1 = UserCreateRequest(
        first_name="Alice",
        last_name="Smith",
        email="alice.smith@example.com",
        password_hash="hash1",
        handle="alicesmith",
        date_of_birth=date(1992, 5, 15),
    )

    user_request2 = UserCreateRequest(
        first_name="Bob",
        last_name="Johnson",
        email="alice.smith@example.com",
        password_hash="hash2",
        handle="bobjohnson",
        date_of_birth=date(1988, 10, 5),
    )

    await repository.create_user(user_request1)

    with pytest.raises(Exception):
        await repository.create_user(user_request2)


@pytest.mark.asyncio
async def test_find_user_by_email(beanie_test_db):
    repository = UserRepository()
    user_request = UserCreateRequest(
        first_name="Jane",
        last_name="Smith",
        email="jane.smith@example.com",
        password_hash="hash",
        handle="janesmith",
        date_of_birth=date(1992, 5, 15),
    )
    created_user = await repository.create_user(user_request)

    found_user = await repository.find_user_by_email("jane.smith@example.com")

    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.email == "jane.smith@example.com"


@pytest.mark.asyncio
async def test_logical_delete_user(beanie_test_db):
    repository = UserRepository()
    user_request = UserCreateRequest(
        first_name="Alice",
        last_name="Johnson",
        email="alice.johnson@example.com",
        password_hash="hash",
        handle="alicej",
        date_of_birth=date(1985, 3, 20),
    )
    created_user = await repository.create_user(user_request)

    deleted = await repository.delete_user(str(created_user.id))

    assert deleted is True
    user = await repository.find_user_by_id(str(created_user.id))
    assert user is None
    raw_user = await User.get(created_user.id)
    assert raw_user is not None
    assert raw_user.deleted is True


@pytest.mark.asyncio
async def test_oblivion_user(beanie_test_db):
    repository = UserRepository()
    user_request = UserCreateRequest(
        first_name="Bob",
        last_name="Williams",
        email="bob.williams@example.com",
        password_hash="hash",
        handle="bobw",
        date_of_birth=date(1988, 10, 5),
    )
    created_user = await repository.create_user(user_request)

    success = await repository.delete_user_oblivion(str(created_user.id))
    user = await User.get(created_user.id)
    assert success is True
    assert user is not None
    assert user.first_name == "Deleted"
    assert user.last_name == "User"
    assert user.email == f"deleted_{created_user.id}@deleted.local"
    assert user.handle == f"deleted_{created_user.id}"
    assert user.date_of_birth is None
    assert user.password_hash is None
    assert user.deleted is True
    assert user.deleted_at is not None


@pytest.mark.asyncio
async def test_oblivion_user_uses_unique_email_for_multiple_users(beanie_test_db):
    repository = UserRepository()
    first = await repository.create_user(
        UserCreateRequest(
            first_name="First",
            last_name="User",
            email="first@example.com",
            password_hash="hash",
            handle="firstuser",
            date_of_birth=date(1990, 1, 1),
        )
    )
    second = await repository.create_user(
        UserCreateRequest(
            first_name="Second",
            last_name="User",
            email="second@example.com",
            password_hash="hash",
            handle="seconduser",
            date_of_birth=date(1990, 1, 1),
        )
    )

    assert await repository.delete_user_oblivion(str(first.id)) is True
    assert await repository.delete_user_oblivion(str(second.id)) is True

    first_after = await User.get(first.id)
    second_after = await User.get(second.id)
    assert first_after is not None
    assert second_after is not None
    assert first_after.email != second_after.email


@pytest.mark.asyncio
async def test_find_user_filters_soft_deleted(beanie_test_db):
    repository = UserRepository()
    created_user = await repository.create_user(
        UserCreateRequest(
            first_name="Deleted",
            last_name="User",
            email="deleted.user@example.com",
            password_hash="hash",
            handle="deleteduser",
            date_of_birth=date(1990, 1, 1),
        )
    )
    assert await repository.delete_user(str(created_user.id)) is True

    assert await repository.find_user_by_id(str(created_user.id)) is None
    assert await repository.find_user_by_email("deleted.user@example.com") is None
    assert await repository.find_user_by_handle("deleteduser") is None


@pytest.mark.asyncio
async def test_find_user_by_handle(beanie_test_db):
    repository = UserRepository()
    user_request = UserCreateRequest(
        first_name="Charlie",
        last_name="Brown",
        email="test@example.com",
        password_hash="hash",
        handle="charliebrown",
        date_of_birth=date(1990, 1, 1),
    )

    created_user = await repository.create_user(user_request)
    found_user = await repository.find_user_by_handle("charliebrown")
    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.handle == "charliebrown"


@pytest.mark.asyncio
async def test_find_user_by_email_or_handle(beanie_test_db):
    repository = UserRepository()
    user_request = UserCreateRequest(
        first_name="David",
        last_name="Smith",
        email="example@example.com",
        password_hash="hash",
        handle="david_smith",
        date_of_birth=date(1990, 1, 1),
    )
    created_user = await repository.create_user(user_request)
    found_user_by_email = await repository.find_user_by_email_or_handle(
        "example@example.com"
    )
    found_user_by_handle = await repository.find_user_by_email_or_handle("david_smith")
    assert found_user_by_email is not None
    assert found_user_by_email.id == created_user.id
    assert found_user_by_email.email == "example@example.com"
    assert found_user_by_handle is not None
    assert found_user_by_handle.id == created_user.id
    assert found_user_by_handle.handle == "david_smith"
    assert found_user_by_email.id == found_user_by_handle.id


@pytest.mark.asyncio
async def test_find_user_by_id_invalid_object_id(beanie_test_db):
    repository = UserRepository()
    result = await repository.find_user_by_id("not-an-object-id")
    assert result is None


@pytest.mark.asyncio
async def test_delete_user_invalid_object_id(beanie_test_db):
    repository = UserRepository()
    deleted = await repository.delete_user("not-an-object-id")
    assert deleted is False


@pytest.mark.asyncio
async def test_update_password(beanie_test_db, user_create_request):
    repository = UserRepository()
    user = await repository.create_user(user_create_request)

    updated = await repository.update_password(user, "updated-hash")
    assert updated.password_hash == "updated-hash"

    fetched = await User.get(user.id)
    assert fetched is not None
    assert fetched.password_hash == "updated-hash"


@pytest.mark.asyncio
async def test_set_and_clear_reset_password_code(beanie_test_db, user_create_request):
    repository = UserRepository()
    user = await repository.create_user(user_create_request)

    expires_at = datetime.now(UTC)
    updated = await repository.set_reset_password_code(user, "ABC123", expires_at)
    assert updated.reset_password_code == "ABC123"
    assert updated.reset_password_expires is not None
    assert updated.reset_password_expires.replace(tzinfo=UTC) <= expires_at.replace(
        tzinfo=UTC
    )

    cleared = await repository.clear_reset_password_code(updated)
    assert cleared.reset_password_code is None
    assert cleared.reset_password_expires is None
