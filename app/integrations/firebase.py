"""
Firebase Admin SDK initialization.
Supports individual environment variables for service account credentials.
"""

import os
import firebase_admin
from firebase_admin import credentials
from typing import Optional


def initialize_firebase_admin() -> Optional[firebase_admin.App]:
    """
    Initialize Firebase Admin SDK using individual environment variables.

    Required environment variables:
    - FIREBASE_PROJECT_ID: Firebase project ID
    - FIREBASE_CLIENT_EMAIL: Service account email
    - FIREBASE_PRIVATE_KEY: Service account private key (with \\n for newlines)

    Optional environment variables:
    - FIREBASE_PRIVATE_KEY_ID: Private key ID
    - FIREBASE_CLIENT_ID: Client ID
    - FIREBASE_DATABASE_URL: Firebase Realtime Database URL
    - FIREBASE_STORAGE_BUCKET: Firebase Storage bucket name

    For emulator mode:
    - FIREBASE_AUTH_EMULATOR_HOST: When set, skips credential validation

    Returns:
        firebase_admin.App instance if initialized, None otherwise
    """
    # Check if Firebase is already initialized
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass  # App not initialized yet, continue

    # Check if using Firebase Emulator (no real credentials needed)
    emulator_host = os.getenv("FIREBASE_AUTH_EMULATOR_HOST")
    if emulator_host:
        project_id = os.getenv("FIREBASE_PROJECT_ID", "demo-cinelog-e2e")
        options = {"projectId": project_id}
        # Initialize without credentials for emulator mode
        return firebase_admin.initialize_app(options=options)

    # Use individual environment variables
    if _has_individual_credentials():
        try:
            service_account_dict = {
                "type": "service_account",
                "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID", ""),
                "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace(
                    "\\n", "\n"
                ),
                "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                "client_id": os.getenv("FIREBASE_CLIENT_ID", ""),
                "auth_uri": os.getenv(
                    "FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"
                ),
                "token_uri": os.getenv(
                    "FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token"
                ),
                "auth_provider_x509_cert_url": os.getenv(
                    "FIREBASE_AUTH_PROVIDER_X509_CERT_URL",
                    "https://www.googleapis.com/oauth2/v1/certs",
                ),
                "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL", ""),
            }
            cred = credentials.Certificate(service_account_dict)
            options = _get_firebase_options()
            return firebase_admin.initialize_app(cred, options)
        except Exception as e:
            raise ValueError(
                f"Failed to initialize Firebase with individual credentials: {e}"
            )

    # If no credentials found, return None (Firebase won't be initialized)
    # This allows the app to run without Firebase if it's optional
    return None


def is_firebase_initialized() -> bool:
    """
    Check if Firebase Admin SDK is initialized.

    Returns:
        True if Firebase is initialized, False otherwise
    """
    try:
        firebase_admin.get_app()
        return True
    except ValueError:
        return False


def _get_firebase_options() -> dict:
    """
    Get Firebase initialization options from environment variables.

    Returns:
        Dictionary of Firebase options
    """
    options = {}

    project_id = os.getenv("FIREBASE_PROJECT_ID")
    if project_id:
        options["projectId"] = project_id

    database_url = os.getenv("FIREBASE_DATABASE_URL")
    if database_url:
        options["databaseURL"] = database_url

    storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
    if storage_bucket:
        options["storageBucket"] = storage_bucket

    return options


def _has_individual_credentials() -> bool:
    """
    Check if all required individual credential environment variables are set.

    Returns:
        True if required credentials are present, False otherwise
    """
    required_vars = [
        "FIREBASE_PROJECT_ID",
        "FIREBASE_CLIENT_EMAIL",
        "FIREBASE_PRIVATE_KEY",
    ]
    return all(os.getenv(var) for var in required_vars)
