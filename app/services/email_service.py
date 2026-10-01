import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@cinelog.app")
        self.logger = logging.getLogger(__name__)

    def _send_email(self, to_email: str, subject: str, text: str, html: str, mock_label: str) -> None:
        if not self.smtp_server:
            self.logger.warning("SMTP not configured. Mock email for %s: %s", to_email, subject)
            print(f"--- EMAIL MOCK ---\nTo: {to_email}\nSubject: {subject}\n{mock_label}\n------------------")
            return

        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.smtp_from_email
            message["To"] = to_email

            part1 = MIMEText(text, "plain")
            part2 = MIMEText(html, "html")

            message.attach(part1)
            message.attach(part2)

            use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true" or self.smtp_port == 465

            if use_ssl:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.ehlo()
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_from_email, to_email, message.as_string())
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.ehlo()
                    if server.has_extn("STARTTLS"):
                        server.starttls()
                        server.ehlo()

                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)

                    server.sendmail(self.smtp_from_email, to_email, message.as_string())

            self.logger.info("Email sent to %s: %s", to_email, subject)

        except Exception as e:
            self.logger.error("Failed to send email to %s: %s", to_email, str(e))
            print(
                "--- EMAIL FAILURE FALLBACK ---\n"
                f"To: {to_email}\n"
                f"Subject: {subject}\n"
                f"{mock_label}\n"
                f"Error: {e}\n"
                "------------------------------"
            )

    def send_reset_password_email(self, to_email: str, code: str):
        """
        Send reset password email via SMTP.
        If SMTP configuration is missing, log the code to console (dev mode).
        """
        text = f"Your password reset code is: {code}\nThis code will expire in 15 minutes."
        html = f"""
        <html>
          <body>
            <p>Your password reset code is: <strong>{code}</strong></p>
            <p>This code will expire in 15 minutes.</p>
          </body>
        </html>
        """
        self._send_email(to_email, "Password Reset - Cinelog", text, html, f"Code: {code}")

    def send_registration_verification_email(self, to_email: str, code: str) -> None:
        """
        Send registration verification email via SMTP.
        If SMTP configuration is missing, log the code to console (dev mode).
        """
        text = f"Your Cinelog registration code is: {code}\nThis code will expire in 15 minutes."
        html = f"""
        <html>
          <body>
            <p>Your Cinelog registration code is: <strong>{code}</strong></p>
            <p>This code will expire in 15 minutes.</p>
          </body>
        </html>
        """
        self._send_email(to_email, "Verify your Cinelog email", text, html, f"Code: {code}")

    def send_registration_existing_account_email(self, to_email: str) -> None:
        """
        Notify a registrant that the submitted email already has an account.
        """
        text = (
            "A Cinelog account already exists for this email address.\n"
            "If this was you, sign in or use password recovery if needed."
        )
        html = """
        <html>
          <body>
            <p>A Cinelog account already exists for this email address.</p>
            <p>If this was you, sign in or use password recovery if needed.</p>
          </body>
        </html>
        """
        self._send_email(to_email, "Cinelog account already exists", text, html, "Existing account notice")
