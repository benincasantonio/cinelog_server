from mongoengine import StringField, DateTimeField, ObjectIdField
from bson import ObjectId

from app.models.base_entity import BaseEntity


class User(BaseEntity):
    id = ObjectIdField(primary_key=True, default=lambda: ObjectId())
    first_name = StringField(db_field="firstName", required=True)
    last_name = StringField(db_field="lastName", required=True)
    email = StringField(required=True, unique=True)
    handle = StringField(required=True, unique=True)
    bio = StringField()
    date_of_birth = DateTimeField(db_field="dateOfBirth")
    firebase_uid = StringField(db_field="firebaseUid", unique=True, sparse=True)

    # Auth fields for local authentication
    password_hash = StringField(db_field="passwordHash")
    reset_password_code = StringField(db_field="resetPasswordCode")
    reset_password_expires = DateTimeField(db_field="resetPasswordExpires")

    meta = {
        "collection": "users",
    }
