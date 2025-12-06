from app.models.base_entity import BaseEntity
from mongoengine import DateTimeField, StringField, ObjectIdField, IntField
from bson import ObjectId

class Log(BaseEntity):
    meta = {
        'collection': 'logs',
        'indexes': [
            'userId',
            'dateWatched',
            {'fields': ['userId', '-dateWatched']},
            {'fields': ['userId', 'movieId']},
            {'fields': ['tmdbId', '-dateWatched']},
            'watchedWhere'
        ]
    }

    id = ObjectIdField(primary_key=True, default=lambda: ObjectId())
    userId = ObjectIdField(required=True)
    movieId = ObjectIdField(required=True)
    tmdbId = IntField(required=True)
    dateWatched = DateTimeField(required=True)
    viewingNotes = StringField()
    posterPath = StringField()
    watchedWhere = StringField(choices=["cinema", "streaming", "homeVideo", "tv", "other"], required=True, default="other")
