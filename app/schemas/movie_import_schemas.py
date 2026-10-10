"""Cinelog movie creation DTO and conversion from complete provider metadata."""

from datetime import date
from typing import Any, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.movie_provider_schemas import MovieMetadataDTO, MovieSourceReferenceDTO


class MovieCreateDTO(BaseModel):
    """Data for the existing storage contract; contains no writable canonical ID."""

    model_config = ConfigDict(extra="forbid")

    source: MovieSourceReferenceDTO
    title: str
    release_date: date | None
    overview: str
    poster_path: str | None
    vote_average: float
    runtime: int | None
    original_language: str
    observed_at: AwareDatetime
    source_payload: dict[str, Any] = Field(repr=False)

    @classmethod
    def from_metadata(cls, metadata: MovieMetadataDTO) -> Self:
        """Select importable fields, retaining observation time and source snapshot."""
        return cls(
            source=metadata.source,
            title=metadata.localized.title,
            release_date=metadata.common.release_date,
            overview=metadata.localized.overview,
            poster_path=metadata.common.poster_path,
            vote_average=metadata.external_rating.value,
            runtime=metadata.common.runtime,
            original_language=metadata.common.original_language,
            observed_at=metadata.observed_at,
            source_payload=metadata.source_payload,
        )
