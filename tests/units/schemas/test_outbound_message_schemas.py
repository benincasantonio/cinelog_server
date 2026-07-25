"""Tests for internal outbound-message (transactional outbox) schemas."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.outbound_message_schemas import OutboundEmailContent, OutboundMessageCreateData
from app.types import OutboundMessageChannel, OutboundMessageKind


def test_outbound_email_content_forbids_extra_fields():
    OutboundEmailContent(subject="Subject", text_body="Text", html_body="<p>Text</p>")

    with pytest.raises(ValidationError):
        OutboundEmailContent(subject="Subject", text_body="Text", html_body="<p>Text</p>", cc="extra@example.com")


def test_outbound_message_create_data_defaults_notification_id_to_none():
    data = OutboundMessageCreateData(
        kind=OutboundMessageKind.REGISTRATION_VERIFICATION,
        channel=OutboundMessageChannel.EMAIL,
        destination="user@example.com",
        subject="Subject",
        text_body="Text",
        html_body="<p>Text</p>",
    )

    assert data.notification_id is None


def test_outbound_message_create_data_accepts_a_notification_id():
    notification_id = uuid4()

    data = OutboundMessageCreateData(
        kind=OutboundMessageKind.NOTIFICATION,
        notification_id=notification_id,
        channel=OutboundMessageChannel.EMAIL,
        destination="user@example.com",
        subject="Subject",
        text_body="Text",
        html_body="<p>Text</p>",
    )

    assert data.notification_id == notification_id


def test_outbound_message_create_data_forbids_extra_fields():
    with pytest.raises(ValidationError):
        OutboundMessageCreateData(
            kind=OutboundMessageKind.REGISTRATION_VERIFICATION,
            channel=OutboundMessageChannel.EMAIL,
            destination="user@example.com",
            subject="Subject",
            text_body="Text",
            html_body="<p>Text</p>",
            unexpected="field",
        )


def test_outbound_message_create_data_rejects_unknown_enum_values():
    with pytest.raises(ValidationError):
        OutboundMessageCreateData(
            kind="unknown_kind",
            channel=OutboundMessageChannel.EMAIL,
            destination="user@example.com",
            subject="Subject",
            text_body="Text",
            html_body="<p>Text</p>",
        )
