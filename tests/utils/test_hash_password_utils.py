from app.utils.hash_password_utils import hash_password, check_password

class TestHashPasswordUtils:
    def test_hash_password(self):
        password = "testpassword"
        hashed_password = hash_password(password)
        assert hashed_password != password
        assert len(hashed_password) > 0

    def test_check_password(self):
        password = "testpassword"
        hashed_password = hash_password(password)
        assert check_password(password, hashed_password) is True
        assert check_password("wrongpassword", hashed_password) is False