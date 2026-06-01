from uuid import UUID

import pytest
from beanie import PydanticObjectId

from app.utils.id_utils import is_valid_uuid, mongo_id_to_uuid


def test_mongo_id_to_uuid_is_deterministic():
    first = mongo_id_to_uuid("507f1f77bcf86cd799439011")
    second = mongo_id_to_uuid("507f1f77bcf86cd799439011")

    assert first == second
    assert first == UUID("e340c5bd-a268-5cb5-9e3c-2413648520da")


def test_mongo_id_to_uuid_is_deterministic_for_generated_object_id():
    mongo_id = PydanticObjectId()

    first = mongo_id_to_uuid(mongo_id)
    second = mongo_id_to_uuid(mongo_id)

    assert first == second


def test_mongo_id_to_uuid_is_collection_independent():
    user_id = mongo_id_to_uuid("507f1f77bcf86cd799439011")
    movie_id = mongo_id_to_uuid("507f1f77bcf86cd799439011")

    assert user_id == movie_id


def test_mongo_id_to_uuid_changes_for_different_object_ids():
    first = mongo_id_to_uuid("507f1f77bcf86cd799439011")
    second = mongo_id_to_uuid("507f1f77bcf86cd799439012")

    assert second == UUID("1e373beb-32e2-59e9-b086-c4bffa7838df")
    assert first != second


def test_mongo_id_to_uuid_accepts_pydantic_object_id():
    mongo_id = PydanticObjectId("507f1f77bcf86cd799439011")

    assert mongo_id_to_uuid(mongo_id) == UUID("e340c5bd-a268-5cb5-9e3c-2413648520da")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("e340c5bd-a268-5cb5-9e3c-2413648520da", True),
        ("not-a-uuid", False),
        ("507f1f77bcf86cd799439011", False),
    ],
)
def test_is_valid_uuid(value: str, expected: bool):
    assert is_valid_uuid(value) is expected
