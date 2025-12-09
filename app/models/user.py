from mongoengine import StringField, DateTimeField, ObjectIdField
from bson import ObjectId

from app.models.base_entity import BaseEntity


class User(BaseEntity):
    id = ObjectIdField(primary_key=True, default=lambda: ObjectId())
    firstName = StringField(required=True)
    lastName = StringField(required=True)
    email = StringField(required=True, unique=True)
    handle = StringField(required=True, unique=True)
    password = StringField(required=True)
    dateOfBirth = DateTimeField()
    firebaseUid = StringField(unique=True, sparse=True)

    meta = {
        'collection': 'users',
    }

