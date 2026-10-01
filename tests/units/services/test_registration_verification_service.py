from unittest.mock import patch

import pytest

from app.config.registration_verification_config import (
    REGISTRATION_VERIFICATION_MAX_ATTEMPTS,
    REGISTRATION_VERIFICATION_TTL_SECONDS,
)
from app.services.registration_verification_service import (
    RegistrationVerificationService,
)
from app.utils.error_codes_utils import ErrorCodes
from app.utils.exceptions_utils import AppException


class FakeVerificationCache:
    def __init__(self):
        self.hashes: dict[str, dict[str, str]] = {}
        self.expires: dict[str, int] = {}
        self.deleted_keys: list[str] = []

    async def hgetall(self, key: str) -> dict[str, str]:
        return self.hashes.get(key, {}).copy()

    async def hset(self, key: str, mapping: dict[str, str | int]) -> int:
        self.hashes[key] = {field: str(value) for field, value in mapping.items()}
        return len(mapping)

    async def hset_with_ttl(self, key: str, mapping: dict[str, str | int], ttl: int) -> int:
        await self.hset(key, mapping)
        await self.expire(key, ttl)
        return len(mapping)

    async def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        value = int(self.hashes[key].get(field, "0")) + amount
        self.hashes[key][field] = str(value)
        return value

    async def expire(self, key: str, ttl: int) -> bool:
        self.expires[key] = ttl
        return True

    async def delete(self, key: str) -> bool:
        self.deleted_keys.append(key)
        return self.hashes.pop(key, None) is not None


@pytest.fixture
def fake_cache():
    return FakeVerificationCache()


@pytest.fixture
def service(fake_cache):
    with patch(
        "app.services.registration_verification_service.CacheService.get_instance",
        return_value=fake_cache,
    ):
        yield RegistrationVerificationService()


class TestRegistrationVerificationService:
    @pytest.mark.asyncio
    async def test_issue_code_stores_hash_only_with_ttl(self, service, fake_cache):
        with patch("app.services.registration_verification_service.secrets.token_hex", return_value="abc123"):
            code = await service.issue_code("User@Example.com ")

        key = service.build_key("user@example.com")
        assert code == "ABC123"
        assert key in fake_cache.hashes
        assert fake_cache.hashes[key]["attempts"] == "0"
        assert fake_cache.hashes[key]["code_hash"] != "ABC123"
        assert "user@example.com" not in key
        assert fake_cache.expires[key] == REGISTRATION_VERIFICATION_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_validate_code_accepts_matching_hash(self, service):
        code = await service.issue_code("user@example.com")

        await service.validate_code("USER@example.com", code.lower())

    @pytest.mark.asyncio
    async def test_validate_code_requires_code(self, service):
        with pytest.raises(AppException) as exc_info:
            await service.validate_code("user@example.com", " ")

        assert exc_info.value.error == ErrorCodes.EMAIL_VERIFICATION_CODE_REQUIRED

    @pytest.mark.asyncio
    async def test_validate_code_rejects_expired_or_missing_code(self, service):
        with pytest.raises(AppException) as exc_info:
            await service.validate_code("user@example.com", "ABC123")

        assert exc_info.value.error == ErrorCodes.EMAIL_VERIFICATION_CODE_EXPIRED

    @pytest.mark.asyncio
    async def test_validate_code_increments_invalid_attempts(self, service, fake_cache):
        await service.issue_code("user@example.com")

        with pytest.raises(AppException) as exc_info:
            await service.validate_code("user@example.com", "WRONG1")

        key = service.build_key("user@example.com")
        assert exc_info.value.error == ErrorCodes.INVALID_EMAIL_VERIFICATION_CODE
        assert fake_cache.hashes[key]["attempts"] == "1"

    @pytest.mark.asyncio
    async def test_validate_code_blocks_when_attempt_limit_reached(self, service, fake_cache):
        await service.issue_code("user@example.com")
        key = service.build_key("user@example.com")
        fake_cache.hashes[key]["attempts"] = str(REGISTRATION_VERIFICATION_MAX_ATTEMPTS)

        with pytest.raises(AppException) as exc_info:
            await service.validate_code("user@example.com", "ABC123")

        assert exc_info.value.error == ErrorCodes.EMAIL_VERIFICATION_CODE_ATTEMPTS_EXCEEDED

    @pytest.mark.asyncio
    async def test_validate_code_rejects_corrupt_attempt_count(self, service, fake_cache):
        await service.issue_code("user@example.com")
        key = service.build_key("user@example.com")
        fake_cache.hashes[key]["attempts"] = "many"

        with pytest.raises(AppException) as exc_info:
            await service.validate_code("user@example.com", "ABC123")

        assert exc_info.value.error == ErrorCodes.EMAIL_VERIFICATION_CODE_EXPIRED

    @pytest.mark.asyncio
    async def test_delete_code_deletes_email_key(self, service, fake_cache):
        await service.issue_code("user@example.com")
        key = service.build_key("user@example.com")

        await service.delete_code("user@example.com")

        assert fake_cache.deleted_keys == [key]
