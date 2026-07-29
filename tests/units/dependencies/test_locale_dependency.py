from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.dependencies.locale_dependency import locale_dependency


@pytest.mark.asyncio
async def test_locale_dependency_prefers_supported_header_without_database_lookup():
    repository = AsyncMock()
    request = SimpleNamespace(headers={"accept-language": "fr-CA, en-US;q=0.8"})

    result = await locale_dependency(request, uuid4(), repository)

    assert result == "fr-FR"
    repository.find_user_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_locale_dependency_uses_saved_locale_when_header_has_no_match():
    user_id = uuid4()
    repository = AsyncMock()
    repository.find_user_by_id.return_value = SimpleNamespace(locale="it-IT")
    request = SimpleNamespace(headers={"accept-language": "de-DE"})

    result = await locale_dependency(request, user_id, repository)

    assert result == "it-IT"
    repository.find_user_by_id.assert_awaited_once_with(user_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("user", [None, SimpleNamespace(locale="invalid"), SimpleNamespace()])
async def test_locale_dependency_falls_back_to_english_for_missing_or_invalid_saved_locale(user):
    repository = AsyncMock()
    repository.find_user_by_id.return_value = user
    request = SimpleNamespace(headers={})

    assert await locale_dependency(request, uuid4(), repository) == "en-US"


@pytest.mark.asyncio
async def test_locale_dependency_propagates_database_errors():
    repository = AsyncMock()
    repository.find_user_by_id.side_effect = RuntimeError("database unavailable")
    request = SimpleNamespace(headers={})

    with pytest.raises(RuntimeError, match="database unavailable"):
        await locale_dependency(request, uuid4(), repository)
