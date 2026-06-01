"""Repository dependency providers and backend activation guardrails."""

from functools import lru_cache

from app.db.postgres import is_postgres_required
from app.repository.movie_repository import MovieRepository
from app.repository.user_repository import UserRepository


class RepositoryActivationError(RuntimeError):
    """Raised when an unsafe repository activation is requested."""


@lru_cache
def get_movie_repository() -> MovieRepository:
    """Return the active movie repository implementation.

    MovieRepository PostgreSQL activation is intentionally blocked in mixed mode
    because LogRepository and MovieRatingRepository still persist/query Mongo
    ObjectId-based movie references.
    """

    if is_postgres_required():
        raise RepositoryActivationError(
            "DB_BACKEND=postgres is not yet safe for MovieRepository activation: "
            "LogRepository and MovieRatingRepository still depend on Mongo ObjectId movie references. "
            "Keep DB_BACKEND=mongo until related repositories are migrated or a compatibility adapter exists."
        )

    return MovieRepository()


@lru_cache
def get_user_repository() -> UserRepository:
    """Return the active user repository implementation.

    UserRepository PostgreSQL activation is intentionally blocked in mixed mode
    because JWT ``sub`` values, auth dependency parsing, user-owned resource
    checks, Redis keys, and Mongo repositories still depend on ObjectId user
    identifiers.
    """

    if is_postgres_required():
        raise RepositoryActivationError(
            "DB_BACKEND=postgres is not yet safe for UserRepository activation: "
            "JWT subjects, auth dependency parsing, caches, and still-active Mongo repositories "
            "depend on Mongo ObjectId user references. Keep DB_BACKEND=mongo until related "
            "repositories and ID adapters are migrated."
        )

    return UserRepository()
