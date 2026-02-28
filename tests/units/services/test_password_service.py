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
