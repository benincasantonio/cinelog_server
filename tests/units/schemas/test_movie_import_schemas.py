from datetime import date
from uuid import uuid4

from app.schemas.movie_import_schemas import MovieCreateDTO
from tests.fakes.movie_provider import OBSERVED_AT, movie_metadata


def test_import_from_metadata_preserves_source_data_without_canonical_identity():
    metadata = movie_metadata(external_id="catalog:42", locale="it-IT")
    metadata.source.source = "other-source"
    metadata.external_rating.source = "other-source"
    metadata.localized.title = "Titolo localizzato"
    metadata.canonical_movie_id = uuid4()
    metadata.source_payload = {"id": "opaque upstream identity", "nested": {"value": 1}}
    original = metadata.model_dump()

    result = MovieCreateDTO.from_metadata(metadata)

    assert result.model_dump() == {
        "source": {"source": "other-source", "external_id": "catalog:42"},
        "title": "Titolo localizzato",
        "release_date": date(2024, 1, 1),
        "overview": "Mocked movie details",
        "poster_path": "/poster.jpg",
        "vote_average": 7.5,
        "runtime": 120,
        "original_language": "en",
        "observed_at": OBSERVED_AT,
        "source_payload": {"id": "opaque upstream identity", "nested": {"value": 1}},
    }
    assert metadata.model_dump() == original


def test_import_from_metadata_preserves_unknown_optional_values():
    metadata = movie_metadata()
    metadata.common.release_date = None
    metadata.common.runtime = None
    metadata.common.poster_path = None

    result = MovieCreateDTO.from_metadata(metadata)

    assert result.release_date is None
    assert result.runtime is None
    assert result.poster_path is None
