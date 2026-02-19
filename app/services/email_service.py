import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@cinelog.app")
        self.logger = logging.getLogger(__name__)

    def send_reset_password_email(self, to_email: str, code: str):
        """
        Send reset password email via SMTP.
        If SMTP configuration is missing, log the code to console (dev mode).
        """
        if not self.smtp_server:
            self.logger.warning(f"SMTP not configured. Reset code for {to_email}: {code}")
            # print to stdout ensuring it's visible in docker logs/console during dev
            print(f"--- EMAIL MOCK ---\nTo: {to_email}\nSubject: Password Reset\nCode: {code}\n------------------")
            return

        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = "Password Reset - Cinelog"
            message["From"] = self.smtp_from_email
            message["To"] = to_email

            text = f"Your password reset code is: {code}\nThis code will expire in 15 minutes."
            html = f"""
            <html>
              <body>
                <p>Your password reset code is: <strong>{code}</strong></p>
                <p>This code will expire in 15 minutes.</p>
              </body>
            </html>
            """

            part1 = MIMEText(text, "plain")
            part2 = MIMEText(html, "html")

            message.attach(part1)
            message.attach(part2)
            
            use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true" or self.smtp_port == 465

            if use_ssl:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    # Explicitly identify ourselves, ensuring AUTH extension is advertised
                    server.ehlo()
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_from_email, to_email, message.as_string())
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    # Identify ourselves to smtp client
                    server.ehlo()
                    # If we can encrypt, do so
                    if server.has_extn("STARTTLS"):
                        server.starttls()
                        server.ehlo() # re-identify after encryption
                    
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    
                    server.sendmail(self.smtp_from_email, to_email, message.as_string())
            
            self.logger.info(f"Reset password email sent to {to_email}")

        except Exception as e:
            self.logger.error(f"Failed to send email to {to_email}: {str(e)}")
            # Fallback log in case of error
            print(f"--- EMAIL FAILURE FALLBACK ---\nTo: {to_email}\nCode: {code}\nError: {e}\n------------------------------")
