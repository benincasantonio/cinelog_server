from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.auth_schemas import RegisterRequest


def _registration_data() -> dict:
    return {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
        "password": "password123",
        "handle": "janedoe",
        "date_of_birth": date(1990, 1, 1),
        "verification_code": "ABC123",
    }


def test_registration_requires_locale():
    with pytest.raises(ValidationError):
        RegisterRequest(**_registration_data())


def test_registration_accepts_and_normalizes_supported_locale():
    request = RegisterRequest(**_registration_data(), locale=" it-it ")

    assert request.locale == "it-IT"


def test_registration_rejects_unsupported_locale():
    with pytest.raises(ValidationError):
        RegisterRequest(**_registration_data(), locale="de-DE")
