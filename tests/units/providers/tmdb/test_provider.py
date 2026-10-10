import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from freezegun import freeze_time

from app.infrastructure.redis import RedisClient
from app.providers.tmdb import TMDBMovieProvider
from app.providers.tmdb import provider as provider_module
from app.providers.tmdb.cache import TMDBCache
from app.providers.tmdb.client import TMDBClient
from app.providers.tmdb.schemas import TMDBDetailsSnapshot, TMDBSearchSnapshot
from app.schemas.movie_provider_schemas import MovieDetailsQuery, MovieSearchQuery
from app.utils.exceptions_utils import AppException

OBSERVED_AT = datetime(2024, 1, 1, 10, tzinfo=UTC)


@pytest_asyncio.fixture
async def integration(details_data, search_data):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=search_data if request.url.path.endswith("search/movie") else details_data)

    cache = AsyncMock(spec=TMDBCache)
    cache.get_search.return_value = None
    cache.get_details.return_value = None, 3
    cache.invalidate_details.return_value = 4
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        yield TMDBMovieProvider(TMDBClient(client=http), cache), cache, calls


async def test_maps_complete_details_and_search_with_provenance(integration):
    provider, cache, calls = integration
    with freeze_time(OBSERVED_AT):
        details = await provider.get_movie_details(MovieDetailsQuery(external_id="550", locale="it-IT"))
        search = await provider.search_movie(MovieSearchQuery(query="Fight Club", locale="fr-FR"))
    assert details.source.source == "tmdb"
    assert details.source.external_id == "550"
    assert details.canonical_movie_id is None
    assert details.common.runtime == 139
    assert details.common.original_language == "en"
    assert details.common.production_companies[0].name == "Studio"
    assert details.common.production_countries[0].iso_3166_1 == "US"
    assert details.common.spoken_languages[0].english_name == "English"
    assert details.localized.locale == "it-IT"
    assert details.localized.genres[0].name == "Drama"
    assert details.external_rating.model_dump() == {"source": "tmdb", "value": 8.4, "scale": 10, "vote_count": 20000}
    assert details.observed_at == OBSERVED_AT
    assert details.source_payload["id"] == 550
    assert search.results[0].localized.locale == "fr-FR"
    assert search.results[0].common.genre_ids == [18, 53]
    assert not hasattr(search.results[0], "observed_at")
    assert search.observed_at == OBSERVED_AT
    assert cache.set_details.await_args.args[2].observed_at == OBSERVED_AT
    assert cache.set_details.await_args.args[3] == 3
    assert len(calls) == 2


async def test_cache_hits_preserve_original_observation(integration, details_data, search_data):
    provider, cache, calls = integration
    cache.get_details.return_value = TMDBDetailsSnapshot(payload=details_data, observed_at=OBSERVED_AT), 3
    cache.get_search.return_value = TMDBSearchSnapshot(payload=search_data, observed_at=OBSERVED_AT)
    with patch.object(provider_module, "datetime") as clock:
        details = await provider.get_movie_details(MovieDetailsQuery(external_id="550"))
        search = await provider.search_movie(MovieSearchQuery(query="film"))
        clock.now.assert_not_called()
    assert details.observed_at == search.observed_at == OBSERVED_AT
    assert calls == []
    cache.set_details.assert_not_awaited()
    cache.set_search.assert_not_awaited()


@pytest.mark.parametrize(
    ("operation", "query", "component_name"),
    [
        ("search_movie", MovieSearchQuery(query="film"), "MovieSearchItemDTO"),
        ("get_movie_details", MovieDetailsQuery(external_id="550"), "MovieCommonDetailsDTO"),
    ],
)
async def test_fresh_observation_is_stamped_once_after_mapping_fields(integration, operation, query, component_name):
    provider, cache, _ = integration
    component_type = getattr(provider_module, component_name)
    completed_at = datetime(2024, 1, 1, 10, 1, tzinfo=UTC)

    with patch.object(provider_module, "datetime") as clock:
        clock.now.return_value = OBSERVED_AT

        def build_component(*args, **kwargs):
            result = component_type(*args, **kwargs)
            clock.now.assert_not_called()
            clock.now.return_value = completed_at
            return result

        with patch.object(provider_module, component_name, side_effect=build_component) as mapped_component:
            result = await getattr(provider, operation)(query)

        mapped_component.assert_called_once()
        clock.now.assert_called_once_with(UTC)

    assert result.observed_at == completed_at
    write = cache.set_search if operation == "search_movie" else cache.set_details
    assert write.await_args.args[2].observed_at == completed_at


@pytest.mark.parametrize("missing", [True, False])
async def test_optional_missing_or_null_is_unknown(integration, details_data, missing):
    for field in ("release_date", "poster_path", "backdrop_path", "runtime", "tagline", "homepage", "imdb_id"):
        if missing:
            details_data.pop(field, None)
        else:
            details_data[field] = None
    provider, _, _ = integration
    result = await provider.get_movie_details(MovieDetailsQuery(external_id="550"))
    assert result.common.release_date is None
    assert result.common.runtime is None
    assert result.common.poster_path is None
    assert result.localized.tagline is None


@pytest.mark.parametrize("date_fields", [{}, {"release_date": None}, {"release_date": ""}])
async def test_unknown_dates_and_numeric_scores_are_normalized(integration, details_data, search_data, date_fields):
    for payload in (details_data, search_data["results"][0]):
        payload.pop("release_date")
        payload.update(date_fields)
        payload["vote_average"] = "8.4"
    provider, cache, _ = integration
    details = await provider.get_movie_details(MovieDetailsQuery(external_id="550"))
    search = await provider.search_movie(MovieSearchQuery(query="film"))
    assert details.common.release_date is None
    assert search.results[0].common.release_date is None
    assert details.external_rating.value == search.results[0].external_rating.value == 8.4
    assert cache.set_details.await_args.args[2].payload.vote_average == 8.4
    assert cache.set_search.await_args.args[2].payload.results[0].vote_average == 8.4


@pytest.mark.parametrize("title_fields", [{}, {"title": None}, {"title": ""}, {"title": " \t\n"}])
@pytest.mark.parametrize("keep_valid_items", [True, False])
async def test_search_filters_untitled_items_on_fresh_and_cached_reads(
    integration, search_data, title_fields, keep_valid_items
):
    original = search_data["results"][0]
    untitled = {**original, "id": 551}
    untitled.pop("title")
    untitled.update(title_fields)
    items = (
        [{**original, "title": " Fight Club "}, untitled, {**original, "id": 552}] if keep_valid_items else [untitled]
    )
    search_data.update(page=2, total_pages=3, total_results=42, results=items)
    provider, cache, calls = integration
    query = MovieSearchQuery(query="film", locale="it-IT")
    with freeze_time(OBSERVED_AT):
        fresh = await provider.search_movie(query)

    assert [item.source.external_id for item in fresh.results] == (["550", "552"] if keep_valid_items else [])
    assert [item.localized.title for item in fresh.results] == (
        [" Fight Club ", "Fight Club"] if keep_valid_items else []
    )
    assert (fresh.page, fresh.total_pages, fresh.total_results) == (2, 3, 42)
    snapshot = cache.set_search.await_args.args[2]
    assert len(snapshot.payload.results) == len(items)
    cache.get_search.return_value = TMDBSearchSnapshot.model_validate(snapshot.model_dump(mode="json"))
    with freeze_time("2024-01-02"):
        cached = await provider.search_movie(query)
    assert cached == fresh
    assert cached.observed_at == OBSERVED_AT
    assert len(calls) == 1
    cache.set_search.assert_awaited_once()


@pytest.mark.parametrize(
    "field", ["id", "overview", "vote_average", "original_title", "original_language", "genre_ids"]
)
async def test_untitled_item_does_not_hide_missing_required_fields(integration, search_data, field):
    malformed = {**search_data["results"][0], "title": None}
    malformed.pop(field)
    search_data["results"].append(malformed)
    provider, cache, _ = integration
    with pytest.raises(AppException) as raised:
        await provider.search_movie(MovieSearchQuery(query="film"))
    assert raised.value.error.error_code == 502
    assert raised.value.error.error_code_name == "MOVIE_PROVIDER_INVALID_RESPONSE"
    cache.set_search.assert_not_awaited()


@pytest.mark.parametrize("field", ["title", "id", "release_date", "vote_average"])
async def test_malformed_search_item_is_not_silently_filtered(integration, search_data, field):
    malformed = {**search_data["results"][0], field: []}
    search_data["results"].append(malformed)
    provider, cache, _ = integration
    with pytest.raises(AppException, match="MOVIE_PROVIDER_INVALID_RESPONSE"):
        await provider.search_movie(MovieSearchQuery(query="film"))
    cache.set_search.assert_not_awaited()


@pytest.mark.parametrize("search", [True, False])
@pytest.mark.parametrize("score", [None, True, "abc", "NaN", "Infinity", -1, "11"])
async def test_invalid_scores_still_produce_provider_errors(integration, details_data, search_data, search, score):
    payload = search_data["results"][0] if search else details_data
    payload["vote_average"] = score
    provider, cache, _ = integration
    operation = "search_movie" if search else "get_movie_details"
    query = MovieSearchQuery(query="film") if search else MovieDetailsQuery(external_id="550")
    with pytest.raises(AppException) as raised:
        await getattr(provider, operation)(query)
    assert raised.value.error.error_code == 502
    assert raised.value.error.error_code_name == "MOVIE_PROVIDER_INVALID_RESPONSE"
    cache.set_search.assert_not_awaited()
    cache.set_details.assert_not_awaited()


async def test_force_refresh_bumps_only_requested_scope(integration):
    provider, cache, calls = integration
    await provider.get_movie_details(MovieDetailsQuery(external_id="550", locale="it-IT", force_refresh=True))
    cache.invalidate_details.assert_awaited_once_with("550", "it-IT")
    cache.get_details.assert_not_awaited()
    assert cache.set_details.await_args.args[3] == 4
    assert len(calls) == 1


async def test_wrong_identity_is_never_cached(integration, details_data):
    details_data["id"] = 999
    provider, cache, _ = integration
    with pytest.raises(AppException, match="MOVIE_PROVIDER_INVALID_RESPONSE"):
        await provider.get_movie_details(MovieDetailsQuery(external_id="550"))
    cache.set_details.assert_not_awaited()


@pytest.mark.parametrize(
    ("operation", "query", "component_name"),
    [
        ("search_movie", MovieSearchQuery(query="film"), "MovieSearchItemDTO"),
        ("get_movie_details", MovieDetailsQuery(external_id="550"), "MovieCommonDetailsDTO"),
    ],
)
async def test_mapping_error_is_never_timestamped_or_cached(integration, operation, query, component_name):
    provider, cache, _ = integration
    with (
        patch.object(provider_module, component_name, side_effect=ValueError("mapping failed")),
        patch.object(provider_module, "datetime") as clock,
    ):
        with pytest.raises(AppException, match="MOVIE_PROVIDER_INVALID_RESPONSE"):
            await getattr(provider, operation)(query)
        clock.now.assert_not_called()
    cache.set_search.assert_not_awaited()
    cache.set_details.assert_not_awaited()


async def test_redis_failure_still_propagates(integration):
    provider, cache, calls = integration
    cache.get_details.side_effect = ConnectionError("Redis unavailable")
    with pytest.raises(ConnectionError, match="Redis unavailable"):
        await provider.get_movie_details(MovieDetailsQuery(external_id="550"))
    assert calls == []


@pytest.mark.parametrize("operation", ["search_movie", "get_movie_details"])
@pytest.mark.parametrize("cached_value", ["{", "{}"])
async def test_corrupt_cache_is_refilled_and_next_read_is_a_hit(operation, cached_value, search_data, details_data):
    search = operation == "search_movie"
    query = MovieSearchQuery(query="film") if search else MovieDetailsQuery(external_id="550")
    key = "cinelog:tmdb:search:v2:en-US:film" if search else "cinelog:tmdb:details:v2:en-US:550:generation:3"
    values = {key: cached_value}

    async def store(key, value, ex):
        values[key] = value

    raw_redis = AsyncMock()
    raw_redis.get.side_effect = values.get
    raw_redis.set.side_effect = store
    raw_redis.hget.return_value = "3"
    with patch("app.infrastructure.redis.aioredis.from_url", return_value=raw_redis):
        redis = RedisClient("redis://localhost", default_ttl=300)

    respond = AsyncMock(return_value=httpx.Response(200, json=search_data if search else details_data))
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        provider = TMDBMovieProvider(TMDBClient(client=http), TMDBCache(redis))
        with freeze_time(OBSERVED_AT):
            fresh = await getattr(provider, operation)(query)
        with freeze_time("2024-01-02"):
            cached = await getattr(provider, operation)(query)

    assert cached == fresh
    assert cached.observed_at == OBSERVED_AT
    snapshot = TMDBSearchSnapshot if search else TMDBDetailsSnapshot
    assert snapshot.model_validate_json(values[key]).observed_at == OBSERVED_AT
    assert json.loads(values[key])["payload"] == (search_data if search else details_data)
    respond.assert_awaited_once()
    raw_redis.set.assert_awaited_once()
    if not search:
        # One generation read per request; the refill must not read it again.
        assert raw_redis.hget.await_count == 2
    raw_redis.hincrby.assert_not_awaited()


@pytest.mark.parametrize("operation", ["search_movie", "get_movie_details"])
@pytest.mark.parametrize(
    ("status", "code"), [(200, "MOVIE_PROVIDER_INVALID_RESPONSE"), (503, "MOVIE_PROVIDER_UNAVAILABLE")]
)
async def test_corrupt_cache_does_not_hide_upstream_errors(operation, status, code):
    redis = AsyncMock(spec=RedisClient)
    redis.hget.return_value = "3"
    redis.get.return_value = {}
    query = MovieSearchQuery(query="film") if operation == "search_movie" else MovieDetailsQuery(external_id="550")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status, json={}))) as http:
        provider = TMDBMovieProvider(TMDBClient(client=http), TMDBCache(redis))
        with pytest.raises(AppException, match=code):
            await getattr(provider, operation)(query)
    redis.set.assert_not_awaited()


@pytest.mark.parametrize("corrupt_cache", [False, True])
async def test_old_request_cannot_repopulate_current_generation(details_data, corrupt_cache):
    values = {"cinelog:tmdb:details:v2:it-IT:550:generation:0": {}} if corrupt_cache else {}
    generations = {}
    entered, resume = asyncio.Event(), asyncio.Event()
    call_count = 0

    async def respond(_request):
        nonlocal call_count
        call_count += 1
        first = call_count == 1
        if first:
            entered.set()
            await resume.wait()
        return httpx.Response(200, json={**details_data, "title": "Old" if first else "New"})

    async def store(key, value, ttl):
        values[key] = value

    async def bump(key, field):
        key = key, field
        generations[key] = generations.get(key, 0) + 1
        return generations[key]

    redis = AsyncMock(spec=RedisClient)
    redis.get.side_effect = lambda key: values.get(key)
    redis.set.side_effect = store
    redis.hget.side_effect = lambda key, field: str(generations[(key, field)]) if (key, field) in generations else None
    redis.hincrby.side_effect = bump
    cache = TMDBCache(redis)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        provider = TMDBMovieProvider(TMDBClient(client=http), cache)
        query = MovieDetailsQuery(external_id="550", locale="it-IT")
        async with asyncio.timeout(3):
            old = asyncio.create_task(provider.get_movie_details(query))
            try:
                await entered.wait()
                fresh = await provider.get_movie_details(query.model_copy(update={"force_refresh": True}))
                resume.set()
                assert (await old).localized.title == "Old"
                assert (await provider.get_movie_details(query)).localized.title == fresh.localized.title == "New"
                assert await cache.get_details("550", "fr-FR") == (None, 0)
                assert await cache.get_details("551", "it-IT") == (None, 0)
            finally:
                resume.set()
                await old
    assert call_count == 2


async def test_borrowed_collaborators_are_not_closed():
    client, cache = AsyncMock(spec=TMDBClient), AsyncMock(spec=TMDBCache)
    provider = TMDBMovieProvider(client, cache)
    await provider.aclose()
    await provider.aclose()
    client.aclose.assert_not_awaited()
    with pytest.raises(RuntimeError, match="closed"):
        await provider.search_movie(MovieSearchQuery(query="film"))


async def test_singleton_owns_client_and_can_restart():
    await TMDBMovieProvider.aclose_all()
    client = AsyncMock(spec=TMDBClient)
    with patch("app.providers.tmdb.provider.TMDBClient", return_value=client):
        first = TMDBMovieProvider.get_instance()
        assert TMDBMovieProvider.get_instance() is first
        await TMDBMovieProvider.aclose_all()
        await TMDBMovieProvider.aclose_all()
        client.aclose.assert_awaited_once()
        second = TMDBMovieProvider.get_instance()
        assert second is not first
        await second.aclose()
        assert TMDBMovieProvider._singleton is None
