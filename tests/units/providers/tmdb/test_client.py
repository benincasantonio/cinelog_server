from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.providers.tmdb.client import TMDB_TIMEOUT, TMDBClient
from app.utils.exceptions_utils import AppException


@pytest.mark.parametrize("locale", ["en-US", "it-IT", "fr-FR"])
async def test_http_auth_locale_timeout_and_dates(details_data, search_data, locale):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=search_data if request.url.path.endswith("search/movie") else details_data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = TMDBClient(api_key="test-api-key", client=http)
        detail = await client.get_movie_details("550", locale)
        search = await client.search_movie("Fight Club", locale)
    assert detail.release_date.isoformat() == "1999-10-15"
    assert search.results[0].id == 550
    assert requests[0].url.path == "/3/movie/550"
    assert requests[1].url.params["query"] == "Fight Club"
    for request in requests:
        assert request.headers["Authorization"] == "Bearer test-api-key"
        assert request.url.params["language"] == locale
        assert set(request.extensions["timeout"].values()) == {TMDB_TIMEOUT}


@pytest.mark.parametrize(
    ("status", "code", "http_code"),
    [
        (404, "PROVIDER_MOVIE_NOT_FOUND", 404),
        (429, "MOVIE_PROVIDER_UNAVAILABLE", 503),
        (500, "MOVIE_PROVIDER_UNAVAILABLE", 503),
        (503, "MOVIE_PROVIDER_UNAVAILABLE", 503),
        (401, "MOVIE_PROVIDER_INVALID_RESPONSE", 502),
        (403, "MOVIE_PROVIDER_INVALID_RESPONSE", 502),
        (302, "MOVIE_PROVIDER_INVALID_RESPONSE", 502),
    ],
)
async def test_upstream_errors_are_safe(status, code, http_code):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(status, text="upstream-secret"))
    ) as http:
        client = TMDBClient(api_key="private-credential", client=http)
        with pytest.raises(AppException) as raised:
            await client.get_movie_details("550", "en-US")
    assert raised.value.error.error_code_name == code
    assert raised.value.error.error_code == http_code
    assert "secret" not in str(raised.value.error)
    assert "credential" not in str(raised.value.error)


async def test_search_404_is_not_a_missing_movie():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(404))) as http:
        with pytest.raises(AppException, match="MOVIE_PROVIDER_INVALID_RESPONSE"):
            await TMDBClient(client=http).search_movie("film", "en-US")


@pytest.mark.parametrize("exception", [httpx.ConnectError, httpx.ReadTimeout])
async def test_transport_errors_do_not_retry(exception):
    calls = []

    def fail(request):
        calls.append(request)
        raise exception("private transport information", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as http:
        with pytest.raises(AppException, match="MOVIE_PROVIDER_UNAVAILABLE"):
            await TMDBClient(client=http).get_movie_details("550", "en-US")
    assert len(calls) == 1


@pytest.mark.parametrize("body", [b"not-json", b"[]", b"null", b"{}"])
async def test_invalid_payload(body):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))) as http:
        with pytest.raises(AppException, match="MOVIE_PROVIDER_INVALID_RESPONSE"):
            await TMDBClient(client=http).get_movie_details("550", "en-US")


@pytest.mark.parametrize(
    ("field", "value"),
    [("runtime", "abc"), ("runtime", -1), ("id", True), ("release_date", "2024-02-30"), ("vote_average", "abc")],
)
async def test_malformed_fields(details_data, field, value):
    details_data[field] = value
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=details_data))
    ) as http:
        with pytest.raises(AppException, match="MOVIE_PROVIDER_INVALID_RESPONSE"):
            await TMDBClient(client=http).get_movie_details("550", "en-US")


@pytest.mark.parametrize("title_fields", [{}, {"title": None}, {"title": ""}, {"title": " \t\n"}, {"title": 123}])
async def test_details_require_a_nonblank_title(details_data, title_fields):
    details_data.pop("title")
    details_data.update(title_fields)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=details_data))
    ) as http:
        with pytest.raises(AppException) as raised:
            await TMDBClient(client=http).get_movie_details("550", "en-US")
    assert raised.value.error.error_code == 502
    assert raised.value.error.error_code_name == "MOVIE_PROVIDER_INVALID_RESPONSE"


@pytest.mark.parametrize("external_id", ["0", "-1", "../550", "abc"])
async def test_invalid_source_identity_does_not_make_http_request(external_id):
    http = AsyncMock(spec=httpx.AsyncClient)
    with pytest.raises(AppException, match="PROVIDER_MOVIE_NOT_FOUND"):
        await TMDBClient(client=http).get_movie_details(external_id, "en-US")
    http.get.assert_not_awaited()


async def test_owned_client_is_closed_once_and_rejects_reads():
    http = AsyncMock(spec=httpx.AsyncClient)
    with patch("app.providers.tmdb.client.httpx.AsyncClient", return_value=http):
        client = TMDBClient()
    await client.aclose()
    await client.aclose()
    http.aclose.assert_awaited_once()
    with pytest.raises(RuntimeError, match="closed"):
        await client.search_movie("film", "en-US")


async def test_borrowed_client_is_not_closed(search_data):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=search_data))
    ) as http:
        client = TMDBClient(client=http)
        await client.aclose()
        assert not http.is_closed
        assert (await client.search_movie("film", "en-US")).total_results == 1


def test_timeout_must_be_bounded(monkeypatch):
    monkeypatch.setattr("app.providers.tmdb.client.TMDB_TIMEOUT", 0)
    with pytest.raises(ValueError, match="positive"):
        TMDBClient()
