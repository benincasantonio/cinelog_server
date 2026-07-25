"""Shared PostgreSQL repository primitives."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_async_session


class RepositoryBase:
    """Base class for repositories that require an async SQLAlchemy session."""

    def __init__(
        self,
        session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]] = get_async_session,
    ):
        self._session_provider = session_provider

    @asynccontextmanager
    async def _unit_of_work(self, session: AsyncSession | None = None) -> AsyncIterator[AsyncSession]:
        """Yield a session, committing only when this repository owns it.

        When a caller passes an existing ``session`` (e.g. a unit of work composing
        several repositories), this method joins that transaction and leaves the
        commit to the caller. When no session is passed, it opens and commits its
        own — the existing single-repository behavior.
        """
        if session is not None:
            yield session
            return

        async with self._session_provider() as owned:
            yield owned
            await owned.commit()
