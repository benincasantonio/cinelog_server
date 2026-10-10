"""Private upstream fixtures for HTTP and provider mapping tests."""

import copy

import pytest

SEARCH_RESULT_DATA = {
    "page": 1,
    "total_results": 1,
    "total_pages": 1,
    "results": [
        {
            "id": 550,
            "title": "Fight Club",
            "overview": "An insomniac office worker...",
            "release_date": "1999-10-15",
            "poster_path": "/poster.jpg",
            "vote_average": 8.4,
            "backdrop_path": "/backdrop.jpg",
            "genre_ids": [18, 53],
            "original_language": "en",
            "original_title": "Fight Club",
        }
    ],
}

DETAILS_DATA = {
    "id": 550,
    "title": "Fight Club",
    "original_title": "Fight Club",
    "overview": "An insomniac office worker...",
    "release_date": "1999-10-15",
    "poster_path": "/poster.jpg",
    "backdrop_path": "/backdrop.jpg",
    "vote_average": 8.4,
    "vote_count": 20000,
    "runtime": 139,
    "budget": 63000000,
    "revenue": 100853753,
    "status": "Released",
    "tagline": "Mischief. Mayhem. Soap.",
    "homepage": "https://www.foxmovies.com/movies/fight-club",
    "imdb_id": "tt0137523",
    "original_language": "en",
    "popularity": 50.5,
    "adult": False,
    "genres": [{"id": 18, "name": "Drama"}],
    "production_companies": [],
    "production_countries": [],
    "spoken_languages": [],
}


@pytest.fixture
def details_data():
    data = copy.deepcopy(DETAILS_DATA)
    data["production_companies"] = [{"id": 1, "name": "Studio", "logo_path": None, "origin_country": "US"}]
    data["production_countries"] = [{"iso_3166_1": "US", "name": "United States"}]
    data["spoken_languages"] = [{"iso_639_1": "en", "name": "English", "english_name": "English"}]
    return data


@pytest.fixture
def search_data():
    return copy.deepcopy(SEARCH_RESULT_DATA)
