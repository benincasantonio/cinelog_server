"""Notification-domain configuration.

Owns the notification cursor scope so the reusable pagination configuration in
``app/config/cursor_pagination_config.py`` stays free of per-domain constants.

The raw prefix is deliberately private: a scope is only ever obtained through
``notification_list_cursor_scope()``, so an inbox cursor cannot accidentally be
signed without its recipient binding.
"""

from uuid import UUID

_NOTIFICATION_LIST_CURSOR_PREFIX = "notifications.list"


def notification_list_cursor_scope(recipient_id: UUID) -> str:
    """Return the recipient-bound signing scope for inbox pagination cursors.

    Binding the recipient into the signed scope means a cursor issued to one
    user is rejected for every other user rather than silently seeking into
    their inbox.
    """

    return f"{_NOTIFICATION_LIST_CURSOR_PREFIX}:{recipient_id}"
