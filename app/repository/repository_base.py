"""Shared PostgreSQL repository primitives."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_async_session


class RepositoryBase:
    """Base class for repositories that require an async SQLAlchemy session."""

    def __init__(
        self,
        session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]] = get_async_session,
    ):
        self._session_provider = session_provider
