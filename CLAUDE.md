# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cinelog is a FastAPI-based movie logging application that allows users to track movies they've watched, rate them, and manage their viewing history. The backend integrates with The Movie Database (TMDB) API for movie information and uses MongoDB with MongoEngine for data persistence.

## Development Commands

### Running the Application

**Local development (with auto-reload):**

```bash
python main.py
```

The API will be available at `http://127.0.0.1:5009`

**Docker Compose (recommended for development):**

```bash
docker-compose -f docker-compose.local.yml up --build
```

This starts both MongoDB and the API service with hot-reload enabled.

### Testing

**Run all tests:**

```bash
pytest
```

**Run tests with coverage:**

```bash
pytest --cov=app --cov-report=html
```

**Run specific test file:**

```bash
pytest tests/services/test_auth_service.py
```

**Run specific test:**

```bash
pytest tests/services/test_auth_service.py::test_function_name
```

### Environment Setup

Required environment variables (see `.env`):

- `JWT_SECRET_KEY`: Secret key for JWT token generation
- `TMDB_API_KEY`: The Movie Database API key
- `MONGODB_HOST`: MongoDB host (default: localhost)
- `MONGODB_PORT`: MongoDB port (default: 27017)
- `MONGODB_DB`: MongoDB database name (default: cinelog_db)

**Firebase Admin SDK Configuration (optional):**

The Firebase Admin SDK is configured using individual environment variables in your `.env` file:

**Required environment variables:**

```bash
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CLIENT_EMAIL=your-service-account@your-project.iam.gserviceaccount.com
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
```

**Optional environment variables:**

```bash
FIREBASE_PRIVATE_KEY_ID=optional-key-id
FIREBASE_CLIENT_ID=optional-client-id
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
```

Note: In the `FIREBASE_PRIVATE_KEY`, use `\n` to represent newlines in the private key.

If no Firebase credentials are provided, the app will run without Firebase (Firebase is optional).

## Architecture

### Layered Architecture

The codebase follows a clean layered architecture:

1. **Controllers** (`app/controllers/`): FastAPI route handlers that define API endpoints
2. **Services** (`app/services/`): Business logic layer that orchestrates repository operations and external integrations (e.g., `AuthService`, `TMDBService`)
3. **Repositories** (`app/repositories/`): Data access layer using MongoEngine ODM
4. **Models** (`app/models/`): MongoEngine document models representing database entities
5. **Schemas** (`app/schemas/`): Pydantic models for request/response validation
6. **Utils** (`app/utils/`): Shared utilities for hashing, JWT tokens, etc.
7. **Integrations** (`app/integrations/`): External service integrations and initialization (e.g., Firebase Admin SDK)

### Key Patterns

**Dependency Flow:**

- Controllers instantiate services with required repositories
- Services contain business logic and call repositories
- Repositories handle direct database operations using MongoEngine models

**Error Handling:**

- Custom `AppException` class with structured `ErrorSchema` objects
- Centralized error codes in `app/utils/error_codes.py`
- Global exception handler in `app/__init__.py` converts `AppException` to JSON responses

**Authentication:**

- JWT-based authentication using access tokens
- `auth_dependency` in `app/dependencies/auth_dependency.py` validates tokens
- Tokens generated via `generate_access_token` in `app/utils/access_token_utils.py`

### Base Entity Pattern

All database models inherit from `BaseEntity` (`app/models/base_entity.py`) which provides:

- Soft delete support (`deleted`, `deletedAt`)
- Automatic timestamps (`createdAt`, `updatedAt`)
- Common indexes

### Data Models

**Core Entities:**

- `User`: User accounts with authentication (email/handle login supported)
- `Movie`: Movie metadata (linked to TMDB via `tmdbId`)
- `Log`: Movie viewing records with ratings, dates, and viewing location
- `MovieRating`: Movie rating collection data

### Testing Approach

Tests use:

- `pytest` for test framework
- `mongomock` for mocking MongoDB in unit tests
- `freezegun` for time-based testing
- Mock pattern for isolating services from repositories

## Important Implementation Details

### User Repository Deletion Methods

The `UserRepository` provides two deletion strategies:

- `delete_user()`: Soft delete (sets `deleted=True`)
- `delete_user_oblivion()`: GDPR-compliant deletion that obscures all user information

### Authentication Flow

1. Login/Register endpoints return JWT token and user info
2. Protected endpoints use `Depends(auth_dependency)` to require authentication
3. Token validation checks expiration and signature using `JWT_SECRET_KEY`

### TMDB Integration

`TMDBService` handles external API calls to The Movie Database:

- Search movies by title
- Returns structured `TMDBMovieSearchResult` Pydantic models

### Firebase Admin Integration

Firebase Admin SDK methods are integrated into `AuthService` for authentication operations. The service includes both in-house authentication methods (login, register) and Firebase Admin methods:

**In-house authentication methods:**

- `login()` - Authenticate user with email/handle and password
- `register()` - Create new user account

**Firebase Admin methods:**

- `is_firebase_initialized()` - Check if Firebase is initialized
- `verify_firebase_id_token()` - Verify Firebase ID tokens
- `get_firebase_user()` - Get user by UID
- `get_firebase_user_by_email()` - Get user by email
- `create_firebase_user()` - Create Firebase user
- `update_firebase_user()` - Update Firebase user
- `delete_firebase_user()` - Delete Firebase user

Firebase Admin SDK is initialized in `app/__init__.py` via `app/integrations/firebase.py` using environment variables. The Firebase methods are available alongside the in-house authentication methods, allowing for a gradual migration to Firebase Authentication.

### MongoDB Connection

Connection is established in `app/__init__.py`:

- Uses environment variables for configuration
- Creates both PyMongo client and MongoEngine connection
- MongoEngine used for ODM operations, PyMongo available if needed
