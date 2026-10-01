import hmac
import secrets
from hashlib import sha256

from app.config.registration_verification_config import (
    REGISTRATION_VERIFICATION_CACHE_PREFIX,
    REGISTRATION_VERIFICATION_HMAC_SECRET,
    REGISTRATION_VERIFICATION_MAX_ATTEMPTS,
    REGISTRATION_VERIFICATION_TTL_SECONDS,
)
from app.services.cache_service import CacheService
from app.utils.auth_utils import normalize_email_identifier, normalize_verification_code
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


class RegistrationVerificationService:
    @property
    def _cache(self) -> CacheService:
        return CacheService.get_instance()

    @staticmethod
    def _hash_value(value: str) -> str:
        return hmac.new(
            REGISTRATION_VERIFICATION_HMAC_SECRET.encode("utf-8"),
            value.encode("utf-8"),
            sha256,
        ).hexdigest()

    @classmethod
    def build_key(cls, email: str) -> str:
        return f"{REGISTRATION_VERIFICATION_CACHE_PREFIX}{cls._hash_value(normalize_email_identifier(email))}"

    @classmethod
    def hash_code(cls, email: str, code: str) -> str:
        normalized_email = normalize_email_identifier(email)
        normalized_code = normalize_verification_code(code)
        return cls._hash_value(f"{normalized_email}:{normalized_code}")

    @staticmethod
    def generate_code() -> str:
        return secrets.token_hex(3).upper()

    async def issue_code(self, email: str) -> str:
        code = self.generate_code()
        key = self.build_key(email)
        await self._cache.hset_with_ttl(
            key,
            {
                "code_hash": self.hash_code(email, code),
                "attempts": 0,
            },
            REGISTRATION_VERIFICATION_TTL_SECONDS,
        )
        return code

    async def validate_code(self, email: str, code: str | None) -> None:
        if code is None or not code.strip():
            raise AppException(ErrorCodes.EMAIL_VERIFICATION_CODE_REQUIRED)

        key = self.build_key(email)
        data = await self._cache.hgetall(key)
        if not data:
            raise AppException(ErrorCodes.EMAIL_VERIFICATION_CODE_EXPIRED)

        code_hash = data.get("code_hash")
        if not code_hash:
            raise AppException(ErrorCodes.EMAIL_VERIFICATION_CODE_EXPIRED)

        try:
            attempts = int(data.get("attempts", "0"))
        except ValueError as exc:
            raise AppException(ErrorCodes.EMAIL_VERIFICATION_CODE_EXPIRED) from exc
        if attempts >= REGISTRATION_VERIFICATION_MAX_ATTEMPTS:
            raise AppException(ErrorCodes.EMAIL_VERIFICATION_CODE_ATTEMPTS_EXCEEDED)

        candidate_hash = self.hash_code(email, code)
        if secrets.compare_digest(code_hash, candidate_hash):
            return

        attempts = await self._cache.hincrby(key, "attempts", 1)
        if attempts >= REGISTRATION_VERIFICATION_MAX_ATTEMPTS:
            raise AppException(ErrorCodes.EMAIL_VERIFICATION_CODE_ATTEMPTS_EXCEEDED)

        raise AppException(ErrorCodes.INVALID_EMAIL_VERIFICATION_CODE)

    async def delete_code(self, email: str) -> None:
        await self._cache.delete(self.build_key(email))
