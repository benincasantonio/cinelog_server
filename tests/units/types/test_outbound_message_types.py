"""Contract tests for closed outbound-message types."""

import pytest

from app.types import OutboundMessageChannel, OutboundMessageKind, OutboundMessageStatus


def test_outbound_message_kind_contains_only_registered_values():
    assert [kind.value for kind in OutboundMessageKind] == [
        "notification",
        "registration_verification",
        "registration_existing_account",
        "password_reset",
    ]


def test_outbound_message_channel_contains_only_registered_values():
    assert [channel.value for channel in OutboundMessageChannel] == ["email"]


def test_outbound_message_status_contains_only_registered_values():
    assert [status.value for status in OutboundMessageStatus] == [
        "pending",
        "processing",
        "delivered",
        "failed",
        "cancelled",
    ]


def test_outbound_message_enums_reject_unknown_values():
    with pytest.raises(ValueError):
        OutboundMessageKind("unknown_kind")

    with pytest.raises(ValueError):
        OutboundMessageChannel("sms")

    with pytest.raises(ValueError):
        OutboundMessageStatus("unknown_status")
