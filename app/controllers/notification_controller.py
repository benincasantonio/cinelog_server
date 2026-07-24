"""Authenticated notification inbox endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.config.rate_limiter import limiter
from app.dependencies.auth_dependency import auth_dependency
from app.dependencies.service_dependency import get_notification_service
from app.schemas.notification_schemas import (
    MarkAllNotificationsReadResponse,
    NotificationBaseResponse,
    NotificationListRequest,
    NotificationListResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("", response_model=NotificationListResponse[NotificationBaseResponse])
@limiter.limit("60/minute")
async def list_notifications(
    request: Request,
    response: Response,
    list_request: Annotated[NotificationListRequest, Query()],
    user_id: UUID = Depends(auth_dependency),
    notification_service: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse[NotificationBaseResponse]:
    """List the authenticated recipient's notification inbox without changing read state."""

    return await notification_service.list_notifications(user_id, list_request)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationBaseResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("60/minute")
async def mark_notification_read(
    request: Request,
    response: Response,
    notification_id: UUID,
    user_id: UUID = Depends(auth_dependency),
    notification_service: NotificationService = Depends(get_notification_service),
) -> NotificationBaseResponse:
    """Idempotently mark one owned notification read using the database timestamp."""

    return await notification_service.mark_notification_read(notification_id, user_id)


@router.post(
    "/read-all",
    response_model=MarkAllNotificationsReadResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("10/minute")
async def mark_all_notifications_read(
    request: Request,
    response: Response,
    user_id: UUID = Depends(auth_dependency),
    notification_service: NotificationService = Depends(get_notification_service),
) -> MarkAllNotificationsReadResponse:
    """Mark all current active unread notifications for the recipient read."""

    return await notification_service.mark_all_notifications_read(user_id)
