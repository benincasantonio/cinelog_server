from mongoengine import Document, StringField, DateTimeField, ObjectIdField
from bson import ObjectId
from datetime import datetime


class User(Document):
    id = ObjectIdField(primary_key=True, default=lambda: ObjectId())
    firstName = StringField(required=True)
    lastName = StringField(required=True)
    email = StringField(required=True, unique=True)
    password = StringField(required=True)
    dateOfBirth = DateTimeField()
    deleted = StringField(default="false")
    deletedAt = DateTimeField()
    createdAt = DateTimeField(default=lambda: datetime.now())

