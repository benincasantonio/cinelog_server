"""
Outbound-message-domain closed enum types.

Types:
    OutboundMessageKind    — registered outbound message content kinds (what is being sent)
    OutboundMessageChannel — registered delivery transports (how it is sent)
    OutboundMessageStatus  — registered lifecycle states of a queued outbound message
"""

from enum import StrEnum


class OutboundMessageKind(StrEnum):
    """Registered outbound message content kinds."""

    NOTIFICATION = "notification"
    REGISTRATION_VERIFICATION = "registration_verification"
    REGISTRATION_EXISTING_ACCOUNT = "registration_existing_account"
    PASSWORD_RESET = "password_reset"  # nosec B105 - message kind identifier, not a credential


class OutboundMessageChannel(StrEnum):
    """Registered outbound message delivery transports."""

    EMAIL = "email"


class OutboundMessageStatus(StrEnum):
    """Registered outbound message lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    # Retired without ever being a delivery problem: the content expired, or a newer
    # message superseded it. Kept distinct from ``failed`` so the operational query for
    # real delivery failures is not swamped by routine code reissues.
    CANCELLED = "cancelled"
