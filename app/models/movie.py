from mongoengine import StringField, IntField
from bson import ObjectId

from app.models.base_entity import BaseEntity


class Movie(BaseEntity):
    id = StringField(primary_key=True, default=lambda: str(ObjectId()))
    tmdbId = IntField(required=True, unique=True)
    title = StringField(required=True)

    meta = {
        'collection': 'movies',
        'indexes': [
            {'fields': ['tmdbId'], 'unique': True}
        ]
    }