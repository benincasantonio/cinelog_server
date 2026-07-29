"""Resolve the locale for authenticated locale-aware requests."""

from uuid import UUID

from fastapi import Depends, Request

from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.repository_dependency import get_user_repository
from app.repository.user_repository_protocol import UserRepositoryProtocol
from app.types import DEFAULT_LOCALE, validate_locale
from app.utils.locale_utils import select_supported_locale


async def locale_dependency(
    request: Request,
    user_id: UUID = Depends(auth_dependency),
    user_repository: UserRepositoryProtocol = Depends(get_user_repository),
) -> str:
    """Resolve locale from the request header, account preference, or default."""

    header_locale = select_supported_locale(request.headers.get("accept-language"))
    if header_locale is not None:
        return header_locale

    user = await user_repository.find_user_by_id(user_id)
    if user is None:
        return DEFAULT_LOCALE

    try:
        return validate_locale(user.locale)
    except (AttributeError, ValueError):
        return DEFAULT_LOCALE
