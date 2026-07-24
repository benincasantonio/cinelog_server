"""
Notification-domain closed enum types.

Types:
    NotificationType   — registered notification identifiers accepted by persistence and API schemas
    NotificationAction — registered actions that a notification response may expose
"""

from enum import StrEnum


class NotificationType(StrEnum):
    """Registered notification identifiers."""

    FOLLOW_STARTED = "follow.started"
    FOLLOW_REQUESTED = "follow.requested"
    FOLLOW_ACCEPTED = "follow.accepted"


class NotificationAction(StrEnum):
    """Registered notification actions."""

    FOLLOW_REQUEST_ACCEPT = "follow_request.accept"
    FOLLOW_REQUEST_REJECT = "follow_request.reject"
