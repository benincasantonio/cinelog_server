import hmac
import os
from hashlib import sha256
from typing import cast

from limits.limits import RateLimitItem
from limits.strategies import RateLimiter

from app.config.auth_rate_limit_config import (
    FORGOT_PASSWORD_ACCOUNT_LIMIT_ITEM,
    FORGOT_PASSWORD_ACCOUNT_RATE_LIMIT_SCOPE,
    LOGIN_ACCOUNT_RATE_LIMIT_SCOPE,
    LOGIN_FAILED_ACCOUNT_LIMIT_ITEM,
    RESET_PASSWORD_ACCOUNT_LIMIT_ITEM,
    RESET_PASSWORD_ACCOUNT_RATE_LIMIT_SCOPE,
)
from app.config.rate_limiter import limiter
from app.utils.error_codes import ErrorCodes
from app.utils.exceptions import AppException

_RATE_LIMIT_HMAC_SECRET = os.getenv("RATE_LIMIT_HMAC_SECRET")
if not _RATE_LIMIT_HMAC_SECRET:
    raise ValueError(
        "RATE_LIMIT_HMAC_SECRET environment variable is not set. Application cannot start."
    )


class AuthRateLimitService:
    @property
    def _limiter(self) -> RateLimiter:
        return limiter.limiter

    def _hit_limit(self, limit_item, scope: str, key: str) -> bool:
        return cast(bool, self._limiter.hit(limit_item, key, scope))

    def _clear_limit(self, limit_item, scope: str, key: str) -> None:
        if scope:
            self._limiter.clear(limit_item, key, scope)
            return

        self._limiter.storage.clear(key)

    def _test_limit(self, limit_item: RateLimitItem, scope: str, key: str) -> bool:
        return self._limiter.test(limit_item, key, scope)

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _hash_identifier(identifier: str) -> str:
        digest = hmac.new(
            cast(str, _RATE_LIMIT_HMAC_SECRET).encode("utf-8"),
            identifier.encode("utf-8"),
            sha256,
        ).hexdigest()
        return digest

    @classmethod
    def build_account_key(cls, email: str) -> str:
        normalized_email = cls._normalize_email(email)
        return f"identifier:{cls._hash_identifier(normalized_email)}"

    def _enforce_account_limit(
        self,
        email: str,
        limit_item: RateLimitItem,
        scope: str,
    ) -> None:
        account_key = self.build_account_key(email)
        allowed = self._test_limit(limit_item, scope, account_key)
        if not allowed:
            raise AppException(ErrorCodes.RATE_LIMIT_EXCEEDED)

    def _register_account_attempt(
        self,
        email: str,
        limit_item: RateLimitItem,
        scope: str,
    ) -> None:
        account_key = self.build_account_key(email)
        allowed = self._hit_limit(limit_item, scope, account_key)
        if not allowed:
            raise AppException(ErrorCodes.RATE_LIMIT_EXCEEDED)

    def enforce_login_failure_limit(self, email: str) -> None:
        self._enforce_account_limit(
            email,
            LOGIN_FAILED_ACCOUNT_LIMIT_ITEM,
            LOGIN_ACCOUNT_RATE_LIMIT_SCOPE,
        )

    def register_login_failure(self, email: str) -> None:
        self._register_account_attempt(
            email,
            LOGIN_FAILED_ACCOUNT_LIMIT_ITEM,
            LOGIN_ACCOUNT_RATE_LIMIT_SCOPE,
        )

    def clear_login_failures(self, email: str) -> None:
        self._clear_limit(
            LOGIN_FAILED_ACCOUNT_LIMIT_ITEM,
            LOGIN_ACCOUNT_RATE_LIMIT_SCOPE,
            self.build_account_key(email),
        )

    def enforce_forgot_password_limit(self, email: str) -> None:
        self._enforce_account_limit(
            email,
            FORGOT_PASSWORD_ACCOUNT_LIMIT_ITEM,
            FORGOT_PASSWORD_ACCOUNT_RATE_LIMIT_SCOPE,
        )

    def register_forgot_password_attempt(self, email: str) -> None:
        self._register_account_attempt(
            email,
            FORGOT_PASSWORD_ACCOUNT_LIMIT_ITEM,
            FORGOT_PASSWORD_ACCOUNT_RATE_LIMIT_SCOPE,
        )

    def enforce_reset_password_limit(self, email: str) -> None:
        self._enforce_account_limit(
            email,
            RESET_PASSWORD_ACCOUNT_LIMIT_ITEM,
            RESET_PASSWORD_ACCOUNT_RATE_LIMIT_SCOPE,
        )

    def register_reset_password_attempt(self, email: str) -> None:
        self._register_account_attempt(
            email,
            RESET_PASSWORD_ACCOUNT_LIMIT_ITEM,
            RESET_PASSWORD_ACCOUNT_RATE_LIMIT_SCOPE,
        )
