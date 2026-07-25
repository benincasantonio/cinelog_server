"""Unit tests for the pure email transport service."""

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_service import EmailDeliveryError, EmailService


def _mock_smtp_context(mock_class: MagicMock) -> MagicMock:
    server = MagicMock()
    server.has_extn.return_value = True
    mock_class.return_value.__enter__.return_value = server
    return server


def test_is_configured_true_for_console_transport(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "console")
    monkeypatch.delenv("SMTP_SERVER", raising=False)

    assert EmailService().is_configured() is True


def test_is_configured_true_when_smtp_server_is_set(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.setenv("SMTP_SERVER", "smtp.example.com")

    assert EmailService().is_configured() is True


def test_is_configured_false_when_smtp_transport_has_no_server(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.delenv("SMTP_SERVER", raising=False)

    assert EmailService().is_configured() is False


def test_console_transport_prints_and_does_not_raise(monkeypatch, capsys):
    monkeypatch.setenv("EMAIL_TRANSPORT", "console")
    monkeypatch.delenv("SMTP_SERVER", raising=False)
    service = EmailService()

    service.send_transactional_email(to_email="user@example.com", subject="Subject", text="Text body", html="<p>x</p>")

    captured = capsys.readouterr()
    assert "user@example.com" in captured.out
    assert "Subject" in captured.out
    assert "Text body" in captured.out


def test_send_transactional_email_raises_when_smtp_server_unset(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.delenv("SMTP_SERVER", raising=False)
    service = EmailService()

    with pytest.raises(EmailDeliveryError):
        service.send_transactional_email(to_email="user@example.com", subject="Subject", text="Text", html="<p>x</p>")


def test_send_transactional_email_passes_timeout_from_env(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.setenv("SMTP_SERVER", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_TIMEOUT_SECONDS", "17")
    monkeypatch.delenv("SMTP_USE_SSL", raising=False)
    service = EmailService()

    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        _mock_smtp_context(mock_smtp)
        service.send_transactional_email(to_email="user@example.com", subject="Subject", text="Text", html="<p>x</p>")

    mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=17)


def test_send_transactional_email_uses_starttls_and_sends_mail(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.setenv("SMTP_SERVER", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")  # nosec B105 - test fixture value, not a real credential
    monkeypatch.delenv("SMTP_USE_SSL", raising=False)
    service = EmailService()

    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        server = _mock_smtp_context(mock_smtp)
        service.send_transactional_email(to_email="user@example.com", subject="Subject", text="Text", html="<p>x</p>")

    server.starttls.assert_called_once()
    server.login.assert_called_once_with("user", "secret")
    server.sendmail.assert_called_once()
    args = server.sendmail.call_args[0]
    assert args[1] == "user@example.com"


def test_send_transactional_email_uses_ssl_for_port_465(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.setenv("SMTP_SERVER", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.delenv("SMTP_USE_SSL", raising=False)
    service = EmailService()

    with patch("app.services.email_service.smtplib.SMTP_SSL") as mock_smtp_ssl:
        _mock_smtp_context(mock_smtp_ssl)
        service.send_transactional_email(to_email="user@example.com", subject="Subject", text="Text", html="<p>x</p>")

    mock_smtp_ssl.assert_called_once_with("smtp.example.com", 465, timeout=10)


def test_send_transactional_email_uses_ssl_when_smtp_use_ssl_env_true(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.setenv("SMTP_SERVER", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USE_SSL", "true")
    service = EmailService()

    with patch("app.services.email_service.smtplib.SMTP_SSL") as mock_smtp_ssl:
        _mock_smtp_context(mock_smtp_ssl)
        service.send_transactional_email(to_email="user@example.com", subject="Subject", text="Text", html="<p>x</p>")

    mock_smtp_ssl.assert_called_once()


def test_send_transactional_email_wraps_smtp_exception(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.setenv("SMTP_SERVER", "smtp.example.com")
    monkeypatch.delenv("SMTP_USE_SSL", raising=False)
    service = EmailService()

    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        server = _mock_smtp_context(mock_smtp)
        server.sendmail.side_effect = smtplib.SMTPException("boom")

        with pytest.raises(EmailDeliveryError):
            service.send_transactional_email(
                to_email="user@example.com", subject="Subject", text="Text", html="<p>x</p>"
            )


def test_send_transactional_email_wraps_os_error(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.setenv("SMTP_SERVER", "smtp.example.com")
    monkeypatch.delenv("SMTP_USE_SSL", raising=False)
    service = EmailService()

    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        mock_smtp.side_effect = OSError("connection refused")

        with pytest.raises(EmailDeliveryError):
            service.send_transactional_email(
                to_email="user@example.com", subject="Subject", text="Text", html="<p>x</p>"
            )
