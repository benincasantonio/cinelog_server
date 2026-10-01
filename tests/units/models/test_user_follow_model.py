"""Model contract tests for accepted directional user follows."""

from sqlalchemy import CheckConstraint

from app.models.user_follow_model import UserFollow


def test_user_follow_model_has_minimal_edge_columns():
    assert set(UserFollow.__table__.columns.keys()) == {
        "follower_id",
        "followed_id",
        "created_at",
    }
    assert [column.name for column in UserFollow.__table__.primary_key.columns] == [
        "follower_id",
        "followed_id",
    ]


def test_user_follow_model_prevents_self_follows_and_indexes_reverse_lookup():
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in UserFollow.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {index.name: index for index in UserFollow.__table__.indexes}

    assert constraints["ck_user_follows_not_self"] == "follower_id <> followed_id"
    assert set(indexes) == {"ix_user_follows_followed_id"}
    assert [column.name for column in indexes["ix_user_follows_followed_id"].columns] == ["followed_id"]
