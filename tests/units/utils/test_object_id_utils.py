from beanie import PydanticObjectId

from app.utils.object_id_utils import to_object_id


class TestToObjectId:
    def test_returns_none_for_none(self):
        assert to_object_id(None) is None

    def test_returns_same_object_id_instance(self):
        object_id = PydanticObjectId("507f1f77bcf86cd799439011")

        assert to_object_id(object_id) is object_id

    def test_parses_valid_object_id_string(self):
        object_id_str = "507f1f77bcf86cd799439011"

        result = to_object_id(object_id_str)

        assert isinstance(result, PydanticObjectId)
        assert str(result) == object_id_str

    def test_returns_none_for_invalid_object_id_string(self):
        assert to_object_id("invalid-object-id") is None
