"""Outbound email content renderers.

Rendering happens once, at enqueue time, and the result is persisted on the
``outbound_messages`` row — it cannot be safely reconstructed later. A registration
or password-reset code exists only as an HMAC hash in Redis once issued (see
``app/services/registration_verification_service.py``), so the plaintext code has to
be captured into the rendered body before it is queued.

Notification email content is rendered from a registry keyed by ``NotificationType``,
one entry per registered type (enforced by a contract test), so a new notification
type without a registered renderer fails loudly instead of silently going unsent.
The shared renderer reuses the persisted ``title``/``body`` text verbatim, which keeps
the emailed content mechanically identical to the in-app inbox with no separate copy
to maintain. Because that text embeds user-supplied values (handles, names), it is
HTML-escaped before being embedded in the HTML body.

Auth renderers (registration verification, existing-account notice, password reset)
reproduce the exact subjects and copy that used to live directly in
``app/services/email_service.py`` before it became a pure transport.
"""

import html
from collections.abc import Callable

from app.models.notification_model import Notification
from app.schemas.outbound_message_schemas import OutboundEmailContent
from app.types import NotificationType

NotificationRenderer = Callable[[Notification], OutboundEmailContent]


def _render_persisted_text(notification: Notification) -> OutboundEmailContent:
    """Render a notification's persisted title/body as email content."""

    escaped_title = html.escape(notification.title)
    escaped_body = html.escape(notification.body)
    html_body = f"<html><body><p><strong>{escaped_title}</strong></p><p>{escaped_body}</p></body></html>"
    return OutboundEmailContent(
        subject=notification.title,
        text_body=notification.body,
        html_body=html_body,
    )


_NOTIFICATION_RENDERERS: dict[NotificationType, NotificationRenderer] = {
    NotificationType.FOLLOW_STARTED: _render_persisted_text,
    NotificationType.FOLLOW_REQUESTED: _render_persisted_text,
    NotificationType.FOLLOW_ACCEPTED: _render_persisted_text,
}


def render_notification_email(notification: Notification) -> OutboundEmailContent | None:
    """Render one notification's email content, or ``None`` when its type is unregistered.

    An unregistered type is a programming error (every ``NotificationType`` member
    must be registered — enforced by a contract test), so the caller is expected to
    raise rather than queue a message that can never be sent.
    """

    renderer = _NOTIFICATION_RENDERERS.get(NotificationType(notification.type))
    if renderer is None:
        return None
    return renderer(notification)


def render_registration_verification(code: str) -> OutboundEmailContent:
    """Render the registration verification email."""

    text_body = f"Your Cinelog registration code is: {code}\nThis code will expire in 15 minutes."
    html_body = f"""
        <html>
          <body>
            <p>Your Cinelog registration code is: <strong>{code}</strong></p>
            <p>This code will expire in 15 minutes.</p>
          </body>
        </html>
        """
    return OutboundEmailContent(subject="Verify your Cinelog email", text_body=text_body, html_body=html_body)


def render_registration_existing_account() -> OutboundEmailContent:
    """Render the existing-account registration notice."""

    text_body = (
        "A Cinelog account already exists for this email address.\n"
        "If this was you, sign in or use password recovery if needed."
    )
    html_body = """
        <html>
          <body>
            <p>A Cinelog account already exists for this email address.</p>
            <p>If this was you, sign in or use password recovery if needed.</p>
          </body>
        </html>
        """
    return OutboundEmailContent(subject="Cinelog account already exists", text_body=text_body, html_body=html_body)


def render_password_reset(code: str) -> OutboundEmailContent:
    """Render the password reset email."""

    text_body = f"Your password reset code is: {code}\nThis code will expire in 15 minutes."
    html_body = f"""
        <html>
          <body>
            <p>Your password reset code is: <strong>{code}</strong></p>
            <p>This code will expire in 15 minutes.</p>
          </body>
        </html>
        """
    return OutboundEmailContent(subject="Password Reset - Cinelog", text_body=text_body, html_body=html_body)
