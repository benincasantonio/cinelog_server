"""
Unit tests for AppException class.
"""

import pytest
from app.utils.exceptions import AppException
from app.utils.error_codes import ErrorCodes


class TestAppException:
    """Tests for AppException class."""

    def test_app_exception_creation(self):
        """Test AppException is created with correct error."""
        exception = AppException(ErrorCodes.USER_NOT_FOUND)
        
        assert exception.error == ErrorCodes.USER_NOT_FOUND
        assert exception.error.error_code_name == "USER_NOT_FOUND"

    def test_app_exception_message(self):
        """Test AppException message comes from error."""
        exception = AppException(ErrorCodes.EMAIL_ALREADY_EXISTS)
        
        assert ErrorCodes.EMAIL_ALREADY_EXISTS.error_message in str(exception.args[0])

    def test_app_exception_str(self):
        """Test AppException __str__ method returns error code name."""
        exception = AppException(ErrorCodes.HANDLE_ALREADY_TAKEN)
        
        result = str(exception)
        
        # __str__ returns a set containing the error_code_name
        assert "HANDLE_ALREADY_TAKEN" in result

    def test_app_exception_is_exception(self):
        """Test AppException is instance of Exception."""
        exception = AppException(ErrorCodes.ERROR_CREATING_USER)
        
        assert isinstance(exception, Exception)

    def test_app_exception_can_be_raised(self):
        """Test AppException can be raised and caught."""
        with pytest.raises(AppException) as exc_info:
            raise AppException(ErrorCodes.USER_NOT_FOUND)
        
        assert exc_info.value.error == ErrorCodes.USER_NOT_FOUND
