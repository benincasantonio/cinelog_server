"""Enqueue-only outbound-message service: thin wrapper over the repository and renderers.

Callers never render content directly — every ``enqueue_*`` method here renders the
right content for its message kind and hands a fully formed row to the repository.
Sending is a separate concern owned by ``OutboundMessageDeliveryService``, so this
service has no SMTP dependency: it can be constructed and exercised with nothing but
the outbound-message repository and the user repository.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_model import Notification
from app.repository.outbound_message_repository_protocol import OutboundMessageRepositoryProtocol
from app.repository.user_repository_protocol import UserRepositoryProtocol
from app.schemas.outbound_message_schemas import OutboundEmailContent, OutboundMessageCreateData
from app.services.outbound_email_renderer import (
    render_notification_email,
    render_password_reset,
    render_registration_existing_account,
    render_registration_verification,
)
from app.types import OutboundMessageChannel, OutboundMessageKind


class OutboundMessageService:
    """Render outbound message content and persist it to the durable outbox.

    Both collaborators are required (no self-defaulting import of the dependency
    providers): this keeps the import graph one-directional — dependency providers in
    ``app/dependencies/`` construct this service, not the other way around.
    """

    def __init__(
        self,
        outbound_message_repository: OutboundMessageRepositoryProtocol,
        user_repository: UserRepositoryProtocol,
    ) -> None:
        self.outbound_message_repository = outbound_message_repository
        self.user_repository = user_repository

    async def enqueue_notification_email(
        self,
        notification: Notification,
        *,
        session: AsyncSession | None = None,
    ) -> UUID | None:
        """Render and enqueue the email delivery for one persisted notification.

        The recipient's email is resolved from the user repository and snapshotted onto
        the queued row at enqueue time, so a later email change on the account does not
        retroactively redirect an already-queued message.
        """

        content = render_notification_email(notification)
        if content is None:
            raise ValueError(f"No email renderer registered for notification type {notification.type!r}")

        recipient = await self.user_repository.find_user_by_id(notification.recipient_id)
        if recipient is None:
            raise ValueError(f"Notification {notification.id} recipient {notification.recipient_id} was not found")

        return await self.outbound_message_repository.enqueue(
            OutboundMessageCreateData(
                kind=OutboundMessageKind.NOTIFICATION,
                notification_id=notification.id,
                channel=OutboundMessageChannel.EMAIL,
                destination=recipient.email,
                subject=content.subject,
                text_body=content.text_body,
                html_body=content.html_body,
            ),
            session=session,
        )

    async def enqueue_registration_verification(self, email: str, code: str) -> UUID | None:
        """Render and enqueue a registration verification code email."""

        content = render_registration_verification(code)
        return await self._enqueue_auth_message(OutboundMessageKind.REGISTRATION_VERIFICATION, email, content)

    async def enqueue_registration_existing_account(self, email: str) -> UUID | None:
        """Render and enqueue an existing-account registration notice email."""

        content = render_registration_existing_account()
        return await self._enqueue_auth_message(OutboundMessageKind.REGISTRATION_EXISTING_ACCOUNT, email, content)

    async def enqueue_password_reset(self, email: str, code: str) -> UUID | None:
        """Render and enqueue a password reset code email."""

        content = render_password_reset(code)
        return await self._enqueue_auth_message(OutboundMessageKind.PASSWORD_RESET, email, content)

    async def _enqueue_auth_message(
        self,
        kind: OutboundMessageKind,
        email: str,
        content: OutboundEmailContent,
    ) -> UUID | None:
        """Enqueue a notification-less (auth-kind) message; these may repeat freely."""

        return await self.outbound_message_repository.enqueue(
            OutboundMessageCreateData(
                kind=kind,
                notification_id=None,
                channel=OutboundMessageChannel.EMAIL,
                destination=email,
                subject=content.subject,
                text_body=content.text_body,
                html_body=content.html_body,
            )
        )
