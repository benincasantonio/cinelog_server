"""Unit tests for outbound email content renderers."""

from uuid import uuid4

from app.models.notification_model import Notification
from app.services.outbound_email_renderer import (
    _NOTIFICATION_RENDERERS,
    render_notification_email,
    render_password_reset,
    render_registration_existing_account,
    render_registration_verification,
)
from app.types import NotificationType


def _notification(*, notification_type: NotificationType, title: str, body: str) -> Notification:
    return Notification(
        recipient_id=uuid4(),
        type=notification_type.value,
        title=title,
        body=body,
    )


def test_every_notification_type_has_a_registered_renderer():
    assert set(_NOTIFICATION_RENDERERS) == set(NotificationType)


def test_render_notification_email_uses_title_as_subject_and_body_verbatim():
    notification = _notification(
        notification_type=NotificationType.FOLLOW_STARTED,
        title="New follower",
        body="A user started following you.",
    )

    content = render_notification_email(notification)

    assert content is not None
    assert content.subject == "New follower"
    assert content.text_body == "A user started following you."


def test_render_notification_email_escapes_title_and_body_in_html():
    notification = _notification(
        notification_type=NotificationType.FOLLOW_REQUESTED,
        title="<b>alice</b> wants to follow you",
        body='Handle: "alice" & <script>alert(1)</script>',
    )

    content = render_notification_email(notification)

    assert content is not None
    assert "<b>alice</b>" not in content.html_body
    assert "<script>" not in content.html_body
    assert "&lt;b&gt;alice&lt;/b&gt;" in content.html_body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content.html_body
    # The plaintext body remains verbatim — escaping is only for the HTML body.
    assert content.text_body == 'Handle: "alice" & <script>alert(1)</script>'


def test_render_notification_email_returns_none_for_an_unregistered_type(monkeypatch):
    monkeypatch.delitem(_NOTIFICATION_RENDERERS, NotificationType.FOLLOW_ACCEPTED)

    notification = _notification(notification_type=NotificationType.FOLLOW_ACCEPTED, title="Title", body="Body")

    assert render_notification_email(notification) is None


def test_render_registration_verification_reproduces_current_subject_and_copy():
    content = render_registration_verification("ABC123")

    assert content.subject == "Verify your Cinelog email"
    assert content.text_body == "Your Cinelog registration code is: ABC123\nThis code will expire in 15 minutes."
    assert "Your Cinelog registration code is: <strong>ABC123</strong>" in content.html_body
    assert "This code will expire in 15 minutes." in content.html_body


def test_render_registration_existing_account_reproduces_current_subject_and_copy():
    content = render_registration_existing_account()

    assert content.subject == "Cinelog account already exists"
    assert content.text_body == (
        "A Cinelog account already exists for this email address.\n"
        "If this was you, sign in or use password recovery if needed."
    )
    assert "A Cinelog account already exists for this email address." in content.html_body
    assert "If this was you, sign in or use password recovery if needed." in content.html_body


def test_render_password_reset_reproduces_current_subject_and_copy():
    content = render_password_reset("XYZ987")

    assert content.subject == "Password Reset - Cinelog"
    assert content.text_body == "Your password reset code is: XYZ987\nThis code will expire in 15 minutes."
    assert "Your password reset code is: <strong>XYZ987</strong>" in content.html_body
    assert "This code will expire in 15 minutes." in content.html_body
