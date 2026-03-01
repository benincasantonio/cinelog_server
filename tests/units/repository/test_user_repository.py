from datetime import date

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
    assert user is not None
    assert user.deleted is True


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
    assert user.email == ""


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
