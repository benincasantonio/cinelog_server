"""
Unit tests for Firebase integration module.
Tests Firebase Admin SDK initialization and helper functions.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os


class TestFirebaseInitialization:
    """Test cases for Firebase initialization functions."""

    @patch('app.integrations.firebase.firebase_admin.get_app')
    def test_initialize_firebase_admin_already_initialized(self, mock_get_app):
        """Test that initialize_firebase_admin returns existing app if already initialized."""
        from app.integrations.firebase import initialize_firebase_admin
        
        mock_app = Mock()
        mock_get_app.return_value = mock_app

        result = initialize_firebase_admin()

        assert result == mock_app
        mock_get_app.assert_called_once()

    @patch('app.integrations.firebase.firebase_admin.initialize_app')
    @patch('app.integrations.firebase.credentials.Certificate')
    @patch('app.integrations.firebase._get_firebase_options')
    @patch('app.integrations.firebase._has_individual_credentials')
    @patch('app.integrations.firebase.firebase_admin.get_app')
    @patch.dict(os.environ, {
        'FIREBASE_PROJECT_ID': 'test-project',
        'FIREBASE_CLIENT_EMAIL': 'test@test.iam.gserviceaccount.com',
        'FIREBASE_PRIVATE_KEY': 'test-key',
        'FIREBASE_PRIVATE_KEY_ID': 'key-id',
        'FIREBASE_CLIENT_ID': 'client-id',
    })
    def test_initialize_firebase_admin_with_credentials(
        self,
        mock_get_app,
        mock_has_creds,
        mock_get_options,
        mock_certificate,
        mock_init_app
    ):
        """Test Firebase initialization with individual credentials."""
        from app.integrations.firebase import initialize_firebase_admin
        
        # Simulate app not initialized yet
        mock_get_app.side_effect = ValueError("No app initialized")
        mock_has_creds.return_value = True
        mock_get_options.return_value = {"projectId": "test-project"}
        mock_cred = Mock()
        mock_certificate.return_value = mock_cred
        mock_app = Mock()
        mock_init_app.return_value = mock_app

        result = initialize_firebase_admin()

        assert result == mock_app
        mock_certificate.assert_called_once()
        mock_init_app.assert_called_once()

    @patch('app.integrations.firebase._has_individual_credentials')
    @patch('app.integrations.firebase.firebase_admin.get_app')
    def test_initialize_firebase_admin_no_credentials(self, mock_get_app, mock_has_creds):
        """Test Firebase initialization returns None when no credentials."""
        from app.integrations.firebase import initialize_firebase_admin
        
        mock_get_app.side_effect = ValueError("No app initialized")
        mock_has_creds.return_value = False

        result = initialize_firebase_admin()

        assert result is None

    @patch('app.integrations.firebase.firebase_admin.initialize_app')
    @patch('app.integrations.firebase.credentials.Certificate')
    @patch('app.integrations.firebase._get_firebase_options')
    @patch('app.integrations.firebase._has_individual_credentials')
    @patch('app.integrations.firebase.firebase_admin.get_app')
    @patch.dict(os.environ, {
        'FIREBASE_PROJECT_ID': 'test-project',
        'FIREBASE_CLIENT_EMAIL': 'test@test.iam.gserviceaccount.com',
        'FIREBASE_PRIVATE_KEY': 'test-key',
    })
    def test_initialize_firebase_admin_exception(
        self,
        mock_get_app,
        mock_has_creds,
        mock_get_options,
        mock_certificate,
        mock_init_app
    ):
        """Test Firebase initialization raises ValueError on exception."""
        from app.integrations.firebase import initialize_firebase_admin
        
        mock_get_app.side_effect = ValueError("No app initialized")
        mock_has_creds.return_value = True
        mock_get_options.return_value = {}
        mock_certificate.side_effect = Exception("Invalid credentials")

        with pytest.raises(ValueError) as exc_info:
            initialize_firebase_admin()

        assert "Failed to initialize Firebase" in str(exc_info.value)


class TestIsFirebaseInitialized:
    """Test cases for is_firebase_initialized function."""

    @patch('app.integrations.firebase.firebase_admin.get_app')
    def test_is_firebase_initialized_true(self, mock_get_app):
        """Test returns True when Firebase is initialized."""
        from app.integrations.firebase import is_firebase_initialized
        
        mock_get_app.return_value = Mock()

        result = is_firebase_initialized()

        assert result is True

    @patch('app.integrations.firebase.firebase_admin.get_app')
    def test_is_firebase_initialized_false(self, mock_get_app):
        """Test returns False when Firebase is not initialized."""
        from app.integrations.firebase import is_firebase_initialized
        
        mock_get_app.side_effect = ValueError("No app initialized")

        result = is_firebase_initialized()

        assert result is False


class TestGetFirebaseOptions:
    """Test cases for _get_firebase_options function."""

    @patch.dict(os.environ, {
        'FIREBASE_PROJECT_ID': 'test-project',
        'FIREBASE_DATABASE_URL': 'https://test.firebaseio.com',
        'FIREBASE_STORAGE_BUCKET': 'test-bucket'
    }, clear=False)
    def test_get_firebase_options_all_present(self):
        """Test returns all options when env vars are present."""
        from app.integrations.firebase import _get_firebase_options
        
        result = _get_firebase_options()

        assert result["projectId"] == "test-project"
        assert result["databaseURL"] == "https://test.firebaseio.com"
        assert result["storageBucket"] == "test-bucket"

    @patch.dict(os.environ, {'FIREBASE_PROJECT_ID': 'test-project'}, clear=True)
    def test_get_firebase_options_only_project_id(self):
        """Test returns only projectId when others are missing."""
        from app.integrations.firebase import _get_firebase_options
        
        result = _get_firebase_options()

        assert result.get("projectId") == "test-project"
        assert "databaseURL" not in result
        assert "storageBucket" not in result

    @patch.dict(os.environ, {}, clear=True)
    def test_get_firebase_options_none_present(self):
        """Test returns empty dict when no env vars are set."""
        from app.integrations.firebase import _get_firebase_options
        
        result = _get_firebase_options()

        assert result == {}


class TestHasIndividualCredentials:
    """Test cases for _has_individual_credentials function."""

    @patch.dict(os.environ, {
        'FIREBASE_PROJECT_ID': 'test-project',
        'FIREBASE_CLIENT_EMAIL': 'test@test.iam.gserviceaccount.com',
        'FIREBASE_PRIVATE_KEY': 'test-key'
    }, clear=True)
    def test_has_individual_credentials_all_present(self):
        """Test returns True when all required vars are present."""
        from app.integrations.firebase import _has_individual_credentials
        
        result = _has_individual_credentials()

        assert result is True

    @patch.dict(os.environ, {
        'FIREBASE_PROJECT_ID': 'test-project',
        'FIREBASE_CLIENT_EMAIL': 'test@test.iam.gserviceaccount.com'
    }, clear=True)
    def test_has_individual_credentials_missing_private_key(self):
        """Test returns False when private key is missing."""
        from app.integrations.firebase import _has_individual_credentials
        
        result = _has_individual_credentials()

        assert result is False

    @patch.dict(os.environ, {}, clear=True)
    def test_has_individual_credentials_none_present(self):
        """Test returns False when no vars are present."""
        from app.integrations.firebase import _has_individual_credentials
        
        result = _has_individual_credentials()

        assert result is False
