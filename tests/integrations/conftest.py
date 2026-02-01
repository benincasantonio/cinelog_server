"""
Integration test fixtures.
Tests controller + service layers with mocked repositories.
No external dependencies (Docker, MongoDB, Firebase) required.
"""
import pytest
from unittest.mock import Mock

from app.repository.user_repository import UserRepository
from app.repository.firebase_auth_repository import FirebaseAuthRepository


@pytest.fixture
def mock_user_repository():
    """Mock UserRepository for integration tests."""
    return Mock(spec=UserRepository)


@pytest.fixture
def mock_firebase_auth_repository():
    """Mock FirebaseAuthRepository for integration tests."""
    return Mock(spec=FirebaseAuthRepository)
