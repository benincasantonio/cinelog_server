"""Pure email transport.

Content is rendered elsewhere — see ``app/services/outbound_email_renderer.py`` for
notification and auth email content, and ``app/services/outbound_message_delivery_service.py``
for the durable-outbox delivery loop that calls ``send_transactional_email``. This module
knows nothing about notifications, registration codes, or password resets.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailDeliveryError(RuntimeError):
    """Raised when an outbound email could not be handed to the configured transport."""


class EmailService:
    """SMTP (or console, for local development) email transport."""

    def __init__(self) -> None:
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@cinelog.app")
        self.smtp_use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true" or self.smtp_port == 465
        self.smtp_timeout_seconds = int(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
        self.transport = os.getenv("EMAIL_TRANSPORT", "smtp")
        self.logger = logging.getLogger(__name__)

    def is_configured(self) -> bool:
        """Return whether this instance can deliver mail without silently discarding it.

        The console transport is always "configured" — it is an explicit opt-in to print
        instead of sending, replacing the old implicit "SMTP unset -> print a mock"
        behavior. The delivery worker uses this to fail fast at startup instead of
        claiming messages it can never deliver.
        """
        return self.transport == "console" or bool(self.smtp_server)

    def send_transactional_email(self, *, to_email: str, subject: str, text: str, html: str) -> None:
        """Send one transactional email, raising ``EmailDeliveryError`` on failure.

        The console transport prints instead of sending and never raises — useful for
        local development without Mailpit. The SMTP transport raises when unconfigured
        or when the underlying send fails, so a caller can retry rather than silently
        losing the message.
        """
        if self.transport == "console":
            print(  # noqa: T20 — explicit dev-mode transport, not a debugging leftover
                f"--- EMAIL (console transport) ---\nTo: {to_email}\nSubject: {subject}\n{text}\n"
                "----------------------------------"
            )
            return

        smtp_server = self.smtp_server
        if not smtp_server:
            raise EmailDeliveryError("SMTP_SERVER is not configured; cannot send email.")

        message = self._build_message(to_email=to_email, subject=subject, text=text, html=html)
        try:
            self._transmit(smtp_server, to_email, message)
        except (smtplib.SMTPException, OSError) as exc:
            self.logger.error("Failed to send email to %s: %s", to_email, exc)
            raise EmailDeliveryError(f"Failed to send email to {to_email}: {exc}") from exc

        self.logger.info("Email sent to %s: %s", to_email, subject)

    def _build_message(self, *, to_email: str, subject: str, text: str, html: str) -> MIMEMultipart:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.smtp_from_email
        message["To"] = to_email
        message.attach(MIMEText(text, "plain"))
        message.attach(MIMEText(html, "html"))
        return message

    def _transmit(self, smtp_server: str, to_email: str, message: MIMEMultipart) -> None:
        if self.smtp_use_ssl:
            with smtplib.SMTP_SSL(smtp_server, self.smtp_port, timeout=self.smtp_timeout_seconds) as server:
                server.ehlo()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_from_email, to_email, message.as_string())
        else:
            with smtplib.SMTP(smtp_server, self.smtp_port, timeout=self.smtp_timeout_seconds) as server:
                server.ehlo()
                if server.has_extn("STARTTLS"):
                    server.starttls()
                    server.ehlo()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_from_email, to_email, message.as_string())
