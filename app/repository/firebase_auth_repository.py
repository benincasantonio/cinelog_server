"""
Repository class for Firebase Authentication operations.
Handles all interactions with Firebase Admin SDK for user authentication.
"""

from firebase_admin import auth
from app.integrations.firebase import is_firebase_initialized
from typing import Optional, Dict, Any


class FirebaseAuthRepository:
    """Repository class for Firebase Authentication operations."""

    def __init__(self):
        pass

    @staticmethod
    def verify_id_token(id_token: str, check_revoked: bool = False) -> Dict[str, Any]:
        """
        Verify and decode a Firebase ID token.

        Args:
            id_token: The Firebase ID token to verify
            check_revoked: Whether to check if the token has been revoked

        Returns:
            Dictionary containing the decoded token claims

        Raises:
            ValueError: If Firebase is not initialized
            auth.InvalidIdTokenError: If the token is invalid
            auth.ExpiredIdTokenError: If the token has expired
            auth.RevokedIdTokenError: If the token has been revoked (when check_revoked=True)
            auth.UserDisabledError: If the user account is disabled
        """
        if not is_firebase_initialized():
            raise ValueError("Firebase Admin SDK is not initialized")

        return auth.verify_id_token(id_token, check_revoked=check_revoked)

    @staticmethod
    def get_user(uid: str) -> auth.UserRecord:
        """
        Get a Firebase user by their UID.

        Args:
            uid: The user ID

        Returns:
            UserRecord object containing user information

        Raises:
            ValueError: If Firebase is not initialized
            auth.UserNotFoundError: If the user does not exist
        """
        if not is_firebase_initialized():
            raise ValueError("Firebase Admin SDK is not initialized")

        return auth.get_user(uid)

    @staticmethod
    def get_user_by_email(email: str) -> auth.UserRecord:
        """
        Get a Firebase user by their email address.

        Args:
            email: The user's email address

        Returns:
            UserRecord object containing user information

        Raises:
            ValueError: If Firebase is not initialized
            auth.UserNotFoundError: If the user does not exist
        """
        if not is_firebase_initialized():
            raise ValueError("Firebase Admin SDK is not initialized")

        return auth.get_user_by_email(email)

    @staticmethod
    def create_user(
        email: Optional[str] = None,
        password: Optional[str] = None,
        uid: Optional[str] = None,
        display_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        email_verified: bool = False,
        disabled: bool = False,
        photo_url: Optional[str] = None,
    ) -> auth.UserRecord:
        """
        Create a new Firebase user.

        Args:
            email: User's email address
            password: User's password
            uid: Custom user ID (optional)
            display_name: User's display name
            phone_number: User's phone number
            email_verified: Whether the email is verified
            disabled: Whether the user account is disabled
            photo_url: URL to user's profile photo

        Returns:
            UserRecord object for the created user

        Raises:
            ValueError: If Firebase is not initialized or required fields are missing
        """
        if not is_firebase_initialized():
            raise ValueError("Firebase Admin SDK is not initialized")

        user_args = {}
        if email:
            user_args["email"] = email
        if password:
            user_args["password"] = password
        if uid:
            user_args["uid"] = uid
        if display_name:
            user_args["display_name"] = display_name
        if phone_number:
            user_args["phone_number"] = phone_number
        if photo_url:
            user_args["photo_url"] = photo_url

        user_args["email_verified"] = email_verified
        user_args["disabled"] = disabled

        return auth.create_user(**user_args)

    @staticmethod
    def update_user(
        uid: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        display_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        email_verified: Optional[bool] = None,
        disabled: Optional[bool] = None,
        photo_url: Optional[str] = None,
    ) -> auth.UserRecord:
        """
        Update an existing Firebase user.

        Args:
            uid: The user ID to update
            email: New email address
            password: New password
            display_name: New display name
            phone_number: New phone number
            email_verified: Whether email is verified
            disabled: Whether account is disabled
            photo_url: New photo URL

        Returns:
            Updated UserRecord object

        Raises:
            ValueError: If Firebase is not initialized
            auth.UserNotFoundError: If the user does not exist
        """
        if not is_firebase_initialized():
            raise ValueError("Firebase Admin SDK is not initialized")

        user_args = {}
        if email is not None:
            user_args["email"] = email
        if password is not None:
            user_args["password"] = password
        if display_name is not None:
            user_args["display_name"] = display_name
        if phone_number is not None:
            user_args["phone_number"] = phone_number
        if email_verified is not None:
            user_args["email_verified"] = email_verified
        if disabled is not None:
            user_args["disabled"] = disabled
        if photo_url is not None:
            user_args["photo_url"] = photo_url

        return auth.update_user(uid, **user_args)

    @staticmethod
    def delete_user(uid: str) -> None:
        """
        Delete a Firebase user by UID.

        Args:
            uid: The user ID to delete

        Raises:
            ValueError: If Firebase is not initialized
            auth.UserNotFoundError: If the user does not exist
        """
        if not is_firebase_initialized():
            raise ValueError("Firebase Admin SDK is not initialized")

        auth.delete_user(uid)
