from datetime import datetime

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.models.user import User


@pytest.mark.asyncio
async def test_user_creation(beanie_test_db):
    user = User(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        date_of_birth="1990-01-01",
        handle="johndoe",
    )
    await user.insert()

    assert await User.find_all().count() == 1


@pytest.mark.asyncio
async def test_required_fields():
    with pytest.raises(Exception):
        User(
            last_name="Doe",
            email="john.doe@example.com",
            date_of_birth="1990-01-01",
            handle="johndoe",
        )


@pytest.mark.asyncio
async def test_email_uniqueness(beanie_test_db):
    user1 = User(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        date_of_birth="1990-01-01",
        handle="johndoe",
    )
    await user1.insert()

    user2 = User(
        first_name="Jane",
        last_name="Smith",
        email="john.doe@example.com",
        date_of_birth="1992-02-02",
        handle="janesmith",
    )
    with pytest.raises(DuplicateKeyError):
        await user2.insert()


@pytest.mark.asyncio
async def test_handle_uniqueness(beanie_test_db):
    user1 = User(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        date_of_birth="1990-01-01",
        handle="johndoe",
    )
    await user1.insert()

    user2 = User(
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        date_of_birth="1992-02-02",
        handle="johndoe",
    )
    with pytest.raises(DuplicateKeyError):
        await user2.insert()


@pytest.mark.asyncio
async def test_created_at_field(beanie_test_db):
    user = User(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        date_of_birth="1990-01-01",
        handle="johndoe",
    )
    await user.insert()

    assert user.created_at is not None
    assert isinstance(user.created_at, datetime)


@pytest.mark.asyncio
async def test_object_id_field(beanie_test_db):
    user = User(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        date_of_birth="1990-01-01",
        handle="johndoe",
    )
    await user.insert()

    assert user.id is not None
    assert isinstance(user.id, ObjectId)
