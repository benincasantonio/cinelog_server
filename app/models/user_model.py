"""PostgreSQL user ORM model."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base_model import BaseEntity
from app.types import PROFILE_VISIBILITY_CHOICES


class User(BaseEntity):
    """User record stored in PostgreSQL."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    handle: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_visibility: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'private'"),
        default="private",
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    reset_password_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    reset_password_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    _profile_visibility_sql = ", ".join(f"'{choice}'" for choice in PROFILE_VISIBILITY_CHOICES)

    __table_args__ = (
        CheckConstraint(
            f"profile_visibility IN ({_profile_visibility_sql})",
            name="ck_users_profile_visibility",
        ),
        Index("uq_users_email_lower", func.lower(email), unique=True),
        Index("uq_users_handle_lower", func.lower(handle), unique=True),
    )
