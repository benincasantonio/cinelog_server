"""Outbound-message (transactional email outbox) internal schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from app.schemas.base_schemas import BaseSchema
from app.types import OutboundMessageChannel, OutboundMessageKind


class StrictOutboundMessageSchema(BaseSchema):
    """Base schema for closed outbound-message contracts."""

    model_config = ConfigDict(extra="forbid")


class OutboundEmailContent(StrictOutboundMessageSchema):
    """Rendered email content produced by a renderer prior to enqueue."""

    subject: str
    text_body: str
    html_body: str


class OutboundMessageCreateData(StrictOutboundMessageSchema):
    """Internal typed input for outbound-message (transactional outbox) persistence."""

    kind: OutboundMessageKind
    notification_id: UUID | None = None
    channel: OutboundMessageChannel
    destination: str
    subject: str
    text_body: str
    html_body: str
    # Set for code-bearing messages so an expired code is discarded rather than
    # delivered by a late retry. ``None`` means the content never goes stale.
    expires_at: datetime | None = None
