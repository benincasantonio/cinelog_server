from fastapi import Response

from app.utils.auth_utils import (
    ACCESS_TOKEN_COOKIE,
    CSRF_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    clear_auth_cookies,
    normalize_email_identifier,
    normalize_verification_code,
)


def test_normalize_email_identifier():
    assert normalize_email_identifier(" User@Example.COM ") == "user@example.com"


def test_normalize_verification_code():
    assert normalize_verification_code(" abc123 ") == "ABC123"


def test_clear_auth_cookies():
    response = Response()
    clear_auth_cookies(response)

    # We can inspect the headers to see if Set-Cookie is present with max-age=0 or expires
    cookies = response.headers.getlist("set-cookie")

    access_cookie_found = False
    refresh_cookie_found = False
    csrf_cookie_found = False

    for cookie in cookies:
        if ACCESS_TOKEN_COOKIE in cookie and "Max-Age=0" in cookie:
            access_cookie_found = True
        if REFRESH_TOKEN_COOKIE in cookie and "Max-Age=0" in cookie:
            refresh_cookie_found = True
        if CSRF_TOKEN_COOKIE in cookie and "Max-Age=0" in cookie:
            csrf_cookie_found = True

    assert access_cookie_found, "access_token cookie should be cleared"
    assert refresh_cookie_found, "refresh_token cookie should be cleared"
    assert csrf_cookie_found, "csrf_token cookie should be cleared"
