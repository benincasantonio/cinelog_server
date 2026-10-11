"""External movie identities and their last persisted provider observation."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, PrimaryKeyConstraint, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import Base
from app.types import MovieProviderName

_provider_sql = ", ".join(f"'{provider.value}'" for provider in MovieProviderName)


class MovieProviderMapping(Base):
    """A durable identity mapping; availability follows the canonical movie."""

    __tablename__ = "movie_providers"

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    movie_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("movies.id"), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("provider", "external_id", name="pk_movie_providers"),
        UniqueConstraint("movie_id", "provider", name="uq_movie_providers_movie_provider"),
        CheckConstraint(f"provider IN ({_provider_sql})", name="ck_movie_providers_provider"),
        CheckConstraint("length(btrim(external_id)) > 0", name="ck_movie_providers_external_id"),
    )
