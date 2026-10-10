"""Deterministic Cinelog provider fake: no HTTP, Redis or upstream DTOs."""

from datetime import UTC, date, datetime

from app.schemas.movie_provider_schemas import (
    ExternalMovieDetailsRatingDTO,
    ExternalMovieRatingDTO,
    MovieCommonDetailsDTO,
    MovieCommonMetadataDTO,
    MovieDetailsQuery,
    MovieLocalizedDetailsDTO,
    MovieLocalizedTextDTO,
    MovieMetadataDTO,
    MovieSearchItemDTO,
    MovieSearchQuery,
    MovieSearchResultDTO,
    MovieSourceReferenceDTO,
)

OBSERVED_AT = datetime(2024, 1, 1, 10, tzinfo=UTC)


def movie_metadata(external_id: str = "550", locale: str = "en-US") -> MovieMetadataDTO:
    return MovieMetadataDTO(
        source=MovieSourceReferenceDTO(source="tmdb", external_id=external_id),
        common=MovieCommonDetailsDTO(
            original_title=f"Movie {external_id}",
            original_language="en",
            release_date=date(2024, 1, 1),
            poster_path="/poster.jpg",
            backdrop_path="/backdrop.jpg",
            genre_ids=[],
            runtime=120,
            budget=50000000,
            revenue=100000000,
            status="Released",
            popularity=50.5,
            adult=False,
            production_companies=[],
            production_countries=[],
            spoken_languages=[],
        ),
        localized=MovieLocalizedDetailsDTO(
            locale=locale,
            title=f"Movie {external_id}",
            overview="Mocked movie details",
            tagline="Mocked tagline",
            genres=[],
        ),
        external_rating=ExternalMovieDetailsRatingDTO(source="tmdb", value=7.5, scale=10, vote_count=1000),
        observed_at=OBSERVED_AT,
        source_payload={"fixture": "opaque snapshot"},
    )


class FakeMovieProvider:
    def __init__(self):
        self.detail_requests: list[MovieDetailsQuery] = []
        self.search_requests: list[MovieSearchQuery] = []

    async def get_movie_details(self, request: MovieDetailsQuery) -> MovieMetadataDTO:
        self.detail_requests.append(request)
        return movie_metadata(request.external_id, request.locale)

    async def search_movie(self, request: MovieSearchQuery) -> MovieSearchResultDTO:
        self.search_requests.append(request)
        metadata = movie_metadata(locale=request.locale)
        return MovieSearchResultDTO(
            page=1,
            total_results=1,
            total_pages=1,
            observed_at=OBSERVED_AT,
            results=[
                MovieSearchItemDTO(
                    source=metadata.source,
                    common=MovieCommonMetadataDTO(**metadata.common.model_dump()),
                    localized=MovieLocalizedTextDTO(**metadata.localized.model_dump()),
                    external_rating=ExternalMovieRatingDTO(source="tmdb", value=7.5, scale=10),
                )
            ],
        )
