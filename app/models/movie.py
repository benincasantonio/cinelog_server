from mongoengine import StringField, IntField, FloatField, DateTimeField
from bson import ObjectId

from app.models.base_entity import BaseEntity


class Movie(BaseEntity):
    id = StringField(primary_key=True, default=lambda: str(ObjectId()))
    tmdb_id = IntField(db_field="tmdbId", required=True, unique=True)
    title = StringField(required=True)
    release_date = DateTimeField(db_field="releaseDate")
    overview = StringField()
    poster_path = StringField(db_field="posterPath")
    vote_average = FloatField(db_field="voteAverage")
    runtime = IntField()
    original_language = StringField(db_field="originalLanguage")

    meta = {
        "collection": "movies",
        "indexes": [{"fields": ["tmdb_id"], "unique": True}],
    }
