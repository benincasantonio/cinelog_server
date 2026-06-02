"""Repository dependency providers and backend activation guardrails."""

from functools import lru_cache

from app.db.postgres import is_postgres_required
from app.repository.log_repository import LogRepository
from app.repository.movie_rating_repository import MovieRatingRepository
from app.repository.movie_repository import MovieRepository
from app.repository.movie_repository_protocol import MovieRepositoryProtocol
from app.repository.postgres_movie_repository import PostgresMovieRepository
from app.repository.postgres_user_repository import PostgresUserRepository
from app.repository.user_repository import UserRepository
from app.repository.user_repository_protocol import UserRepositoryProtocol


class RepositoryActivationError(RuntimeError):
    """Raised when an unsafe repository activation is requested."""


@lru_cache
def get_movie_repository() -> MovieRepositoryProtocol:
    """Return the active movie repository implementation.

    MovieRepository PostgreSQL activation is intentionally blocked in mixed mode
    because LogRepository and MovieRatingRepository still persist/query Mongo
    ObjectId-based movie references.
    """

    if is_postgres_required():
        return PostgresMovieRepository()

    return MovieRepository()


@lru_cache
def get_user_repository() -> UserRepositoryProtocol:
    """Return the active user repository implementation.

    UserRepository PostgreSQL activation is intentionally blocked in mixed mode
    because JWT ``sub`` values, auth dependency parsing, user-owned resource
    checks, Redis keys, and Mongo repositories still depend on ObjectId user
    identifiers.
    """

    if is_postgres_required():
        return PostgresUserRepository()

    return UserRepository()


@lru_cache
def get_movie_rating_repository() -> MovieRatingRepository:
    """Return the active movie-rating repository implementation.

    MovieRatingRepository PostgreSQL activation is intentionally blocked in
    mixed mode because auth still provides Mongo ObjectId user identifiers,
    LogRepository still consumes ObjectId movie references, and MovieRepository
    activation remains blocked until later cutover work.
    """

    if is_postgres_required():
        raise RepositoryActivationError(
            "DB_BACKEND=postgres is not yet safe for MovieRatingRepository activation: "
            "auth still provides Mongo ObjectId user IDs, LogRepository still depends on "
            "Mongo ObjectId movie references, and MovieRepository cutover remains blocked. "
            "Keep DB_BACKEND=mongo until related repositories and ID adapters are migrated."
        )

    return MovieRatingRepository()


@lru_cache
def get_log_repository() -> LogRepository:
    """Return the active log repository implementation.

    LogRepository PostgreSQL activation is intentionally blocked in mixed mode
    because log caching, service wiring, and UUID/ObjectId runtime assumptions
    still require the later cutover work.
    """

    if is_postgres_required():
        raise RepositoryActivationError(
            "DB_BACKEND=postgres is not yet safe for LogRepository activation: "
            "LogCacheRepository and downstream services still rely on Mongo-shaped log caching "
            "and mixed UUID/ObjectId runtime assumptions. Keep DB_BACKEND=mongo until the "
            "repository cutover work is complete."
        )

    return LogRepository()
