from mongoengine import Document, DateTimeField, BooleanField
from datetime import datetime


class BaseEntity(Document):
    """
    Abstract base class that provides common fields for all entity models
    """
    meta = {'abstract': True}
    
    deleted = BooleanField(default=False)
    deletedAt = DateTimeField()
    createdAt = DateTimeField(default=lambda: datetime.now())
    updatedAt = DateTimeField(default=lambda: datetime.now())