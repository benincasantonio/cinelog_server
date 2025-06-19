from app.models.base_entity import BaseEntity
from mongoengine import DateTimeField, StringField, ObjectIdField, IntField
from bson import ObjectId

class Log(BaseEntity):
    meta = {
        'collection': 'logs',
        'indexes': [
            'dateWatched',
            {'fields': ['tmdbId', '-dateWatched']},
            {'fields': ['tmdbId', 'rating']},
            'watchedWhere',
            'dateWatched'
        ]
    }

    id = ObjectIdField(primary_key=True, default=lambda: ObjectId())
    movieId = ObjectIdField(required=True)
    tmdbId = IntField(required=True)
    dateWatched = DateTimeField(required=True)
    comment = StringField()
    rating = IntField(min_value=1, max_value=10)
    posterPath = StringField()
    watchedWhere = StringField(choices=["cinema", "streaming", "homeVideo", "tv", "other"], required=True, default="other")
