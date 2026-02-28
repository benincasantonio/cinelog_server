from app.models.base_entity import BaseEntity
from mongoengine import DateTimeField, StringField, ObjectIdField, IntField
from bson import ObjectId


class Log(BaseEntity):
    meta = {
        "collection": "logs",
        "indexes": [
            "user_id",
            "date_watched",
            {"fields": ["user_id", "-date_watched"]},
            {"fields": ["user_id", "movie_id"]},
            {"fields": ["tmdb_id", "-date_watched"]},
            "watched_where",
        ],
    }

    id = ObjectIdField(primary_key=True, default=lambda: ObjectId())
    user_id = ObjectIdField(db_field="userId", required=True)
    movie_id = ObjectIdField(db_field="movieId", required=True)
    tmdb_id = IntField(db_field="tmdbId", required=True)
    date_watched = DateTimeField(db_field="dateWatched", required=True)
    viewing_notes = StringField(db_field="viewingNotes")
    poster_path = StringField(db_field="posterPath")
    watched_where = StringField(
        db_field="watchedWhere",
        choices=["cinema", "streaming", "homeVideo", "tv", "other"],
        required=True,
        default="other",
    )
