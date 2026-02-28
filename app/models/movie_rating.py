from mongoengine import StringField, ObjectIdField, IntField

from app.models.base_entity import BaseEntity
from bson import ObjectId


class MovieRating(BaseEntity):
    id = ObjectIdField(primary_key=True, default=lambda: ObjectId())
    movie_id = ObjectIdField(db_field="movieId", required=True)
    review = StringField()
    rating = IntField(min_value=1, max_value=10)
    user_id = ObjectIdField(db_field="userId", required=True)
    tmdb_id = IntField(db_field="tmdbId", required=True)

    meta = {
        "collection": "movie_ratings",
        "indexes": [
            {"fields": ["movie_id"]},
            {"fields": ["rating"]},
            {"fields": ["tmdb_id"]},
            {"fields": ["user_id", "tmdb_id"], "unique": True},
        ],
    }
