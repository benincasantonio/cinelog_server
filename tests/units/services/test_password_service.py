import pytest

from app.services.password_service import PasswordService


class TestPasswordService:
    def test_hash_password(self):
        password = "secure_password"
        hashed = PasswordService.get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        password = "secure_password"
        hashed = PasswordService.get_password_hash(password)

        assert PasswordService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        password = "secure_password"
        hashed = PasswordService.get_password_hash(password)

        assert PasswordService.verify_password("wrong_password", hashed) is False

    @pytest.mark.parametrize("password", ["a" * 72, "é" * 36, "🔐" * 18])
    def test_hash_and_verify_72_bytes(self, password):
        hashed = PasswordService.get_password_hash(password)

        assert PasswordService.verify_password(password, hashed) is True
        assert PasswordService.verify_password(password + "suffix", hashed) is False

    @pytest.mark.parametrize("password", ["a" * 73, "a" + "é" * 36])
    def test_hash_rejects_more_than_72_bytes(self, password):
        with pytest.raises(ValueError, match="72 bytes"):
            PasswordService.get_password_hash(password)

    @pytest.mark.parametrize("password", ["a" * 128, "é" * 64, "a" * 71 + "é", "a" * 71 + "🔐"])
    def test_verify_rejects_more_than_72_bytes(self, password):
        hashed = PasswordService.get_password_hash("correct-password")

        assert PasswordService.verify_password(password, hashed) is False
