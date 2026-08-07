from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.dependencies.locale_dependency import locale_dependency


@pytest.mark.asyncio
async def test_locale_dependency_prefers_supported_header_without_service_lookup():
    user_service = AsyncMock()
    request = SimpleNamespace(headers={"accept-language": "fr-CA, en-US;q=0.8"})

    result = await locale_dependency(request, uuid4(), user_service)

    assert result == "fr-FR"
    user_service.get_locale.assert_not_awaited()


@pytest.mark.asyncio
async def test_locale_dependency_uses_saved_locale_when_header_has_no_match():
    user_id = uuid4()
    user_service = AsyncMock()
    user_service.get_locale.return_value = "it-IT"
    request = SimpleNamespace(headers={"accept-language": "de-DE"})

    result = await locale_dependency(request, user_id, user_service)

    assert result == "it-IT"
    user_service.get_locale.assert_awaited_once_with(user_id)


@pytest.mark.asyncio
async def test_locale_dependency_falls_back_to_english_for_missing_user():
    user_service = AsyncMock()
    user_service.get_locale.return_value = None
    request = SimpleNamespace(headers={})

    assert await locale_dependency(request, uuid4(), user_service) == "en-US"


@pytest.mark.asyncio
async def test_locale_dependency_propagates_service_errors():
    user_service = AsyncMock()
    user_service.get_locale.side_effect = RuntimeError("database unavailable")
    request = SimpleNamespace(headers={})

    with pytest.raises(RuntimeError, match="database unavailable"):
        await locale_dependency(request, uuid4(), user_service)
