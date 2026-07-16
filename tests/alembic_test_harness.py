"""Reusable helpers for testing Alembic revisions against PostgreSQL."""

from dataclasses import dataclass

import psycopg
from alembic.config import Config

from alembic import command

PostgresConnectionParams = dict[str, str | int]


@dataclass(frozen=True)
class AlembicTestHarness:
    """Run Alembic commands and direct SQL against an isolated test database."""

    config: Config
    connection_params: PostgresConnectionParams

    def upgrade(self, revision: str = "head") -> None:
        """Upgrade the isolated database to a revision."""
        command.upgrade(self.config, revision)

    def downgrade(self, revision: str) -> None:
        """Downgrade the isolated database to a revision."""
        command.downgrade(self.config, revision)

    def connect(self) -> psycopg.Connection:
        """Open a synchronous connection for seeding and assertions."""
        return psycopg.connect(**self.connection_params)
