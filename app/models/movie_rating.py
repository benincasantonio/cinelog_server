from dataclasses import fields

from mongoengine import StringField, ObjectIdField, IntField

from app.models.base_entity import BaseEntity
from bson import ObjectId


class MovieRating(BaseEntity):
    id: ObjectIdField(primary_key=True, default= lambda: ObjectId())
    movieId: ObjectIdField(required=True, unique=True)
    review: StringField()
    rating = IntField(min_value=1, max_value=10)

    meta = {
        'collection': 'movie_ratings',
        'indexes': [
            {'fields': ['movieId'], 'unique': True},
            {'fields': ['rating']}
        ]
    }