"""Resolve the locale for authenticated locale-aware requests."""

from uuid import UUID

from fastapi import Depends, Request

from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_user_service
from app.services.user_service import UserService
from app.types import DEFAULT_LOCALE
from app.utils.locale_utils import select_supported_locale


async def locale_dependency(
    request: Request,
    user_id: UUID = Depends(auth_dependency),
    user_service: UserService = Depends(get_user_service),
) -> str:
    """Resolve locale from the request header, account preference, or default."""

    header_locale = select_supported_locale(request.headers.get("accept-language"))
    if header_locale is not None:
        return header_locale

    locale = await user_service.get_locale(user_id)
    return locale if locale is not None else DEFAULT_LOCALE
