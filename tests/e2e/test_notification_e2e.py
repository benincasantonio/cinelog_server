"""End-to-end notification inbox and read-state coverage."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text

from tests.e2e.conftest import register, register_and_login


async def _user_id(postgres_engine, email: str) -> UUID:
    async with postgres_engine.connect() as connection:
        row = (await connection.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email})).fetchone()
    assert row is not None
    return row[0]


async def _seed_notification(
    postgres_engine,
    *,
    recipient_id: UUID,
    actor_id: UUID | None,
    notification_type: str,
    title: str,
    created_at: datetime,
) -> UUID:
    async with postgres_engine.begin() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    INSERT INTO notifications (recipient_id, actor_id, type, title, body, created_at, updated_at)
                    VALUES (:recipient_id, :actor_id, :type, :title, 'Notification body', :created_at, :created_at)
                    RETURNING id
                    """
                ),
                {
                    "recipient_id": recipient_id,
                    "actor_id": actor_id,
                    "type": notification_type,
                    "title": title,
                    "created_at": created_at,
                },
            )
        ).fetchone()
    assert row is not None
    return row[0]


async def test_inbox_cursor_is_rejected_for_another_recipient(async_client, postgres_engine):
    owner_data = {
        "email": "cursor-owner@example.com",
        "password": "securepassword123",
        "firstName": "Cursor",
        "lastName": "Owner",
        "handle": "cursorowner",
        "dateOfBirth": "1990-01-01",
        "profileVisibility": "public",
    }
    intruder_data = {
        "email": "cursor-intruder@example.com",
        "password": "securepassword123",
        "firstName": "Cursor",
        "lastName": "Intruder",
        "handle": "cursorintruder",
        "dateOfBirth": "1990-01-01",
        "profileVisibility": "public",
    }
    await register_and_login(async_client, owner_data)
    await register(async_client, intruder_data)
    owner_id = await _user_id(postgres_engine, owner_data["email"])
    intruder_id = await _user_id(postgres_engine, intruder_data["email"])
    now = datetime.now(UTC)
    for offset in range(2):
        await _seed_notification(
            postgres_engine,
            recipient_id=owner_id,
            actor_id=None,
            notification_type="follow.started",
            title=f"Owner {offset}",
            created_at=now - timedelta(minutes=offset),
        )
    await _seed_notification(
        postgres_engine,
        recipient_id=intruder_id,
        actor_id=None,
        notification_type="follow.started",
        title="Intruder",
        created_at=now,
    )

    owner_page = await async_client.get("/v1/notifications", params={"limit": 1})
    assert owner_page.status_code == 200
    stolen_cursor = owner_page.json()["nextCursor"]
    assert stolen_cursor is not None

    login = await async_client.post(
        "/v1/auth/login",
        json={"email": intruder_data["email"], "password": intruder_data["password"]},
    )
    assert login.status_code == 200

    replayed = await async_client.get("/v1/notifications", params={"cursor": stolen_cursor})

    assert replayed.status_code == 422
    assert replayed.json()["error_code_name"] == "INVALID_PAGINATION_CURSOR"

    own_page = await async_client.get("/v1/notifications")
    assert own_page.status_code == 200
    assert [item["title"] for item in own_page.json()["items"]] == ["Intruder"]


async def test_notification_inbox_pagination_authorization_and_read_state(async_client, postgres_engine):
    recipient_data = {
        "email": "notification-recipient@example.com",
        "password": "securepassword123",
        "firstName": "Notification",
        "lastName": "Recipient",
        "handle": "notifrecipient",
        "dateOfBirth": "1990-01-01",
        "profileVisibility": "public",
    }
    actor_data = {
        "email": "notification-actor@example.com",
        "password": "securepassword123",
        "firstName": "Notification",
        "lastName": "Actor",
        "handle": "notificationactor",
        "dateOfBirth": "1990-01-01",
        "profileVisibility": "public",
    }
    login = await register_and_login(async_client, recipient_data)
    await register(async_client, actor_data)
    recipient_id = await _user_id(postgres_engine, recipient_data["email"])
    actor_id = await _user_id(postgres_engine, actor_data["email"])
    now = datetime.now(UTC)
    newest_id = await _seed_notification(
        postgres_engine,
        recipient_id=recipient_id,
        actor_id=actor_id,
        notification_type="follow.started",
        title="Newest",
        created_at=now,
    )
    middle_id = await _seed_notification(
        postgres_engine,
        recipient_id=recipient_id,
        actor_id=actor_id,
        notification_type="follow.requested",
        title="Middle",
        created_at=now - timedelta(minutes=1),
    )
    oldest_id = await _seed_notification(
        postgres_engine,
        recipient_id=recipient_id,
        actor_id=None,
        notification_type="follow.accepted",
        title="Oldest",
        created_at=now - timedelta(minutes=2),
    )
    foreign_id = await _seed_notification(
        postgres_engine,
        recipient_id=actor_id,
        actor_id=recipient_id,
        notification_type="follow.started",
        title="Foreign",
        created_at=now,
    )

    first_page = await async_client.get("/v1/notifications", params={"limit": 2})
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert [item["id"] for item in first_payload["items"]] == [str(newest_id), str(middle_id)]
    assert first_payload["unreadCount"] == 3
    assert first_payload["nextCursor"] is not None
    assert first_payload["items"][0]["actor"] == {
        "handle": "notificationactor",
        "firstName": "Notification",
        "lastName": "Actor",
    }
    assert first_payload["items"][0]["availableActions"] == []

    second_page = await async_client.get(
        "/v1/notifications",
        params={"limit": 2, "cursor": first_payload["nextCursor"]},
    )
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()["items"]] == [str(oldest_id)]
    assert second_page.json()["unreadCount"] == 3

    async with postgres_engine.connect() as connection:
        unread_before = (
            await connection.execute(
                text("SELECT count(*) FROM notifications WHERE recipient_id = :recipient_id AND read_at IS NULL"),
                {"recipient_id": recipient_id},
            )
        ).scalar_one()
    assert unread_before == 3

    first_read = await async_client.patch(
        f"/v1/notifications/{newest_id}/read",
        headers={"X-CSRF-Token": login["csrfToken"]},
    )
    repeated_read = await async_client.patch(
        f"/v1/notifications/{newest_id}/read",
        headers={"X-CSRF-Token": login["csrfToken"]},
    )
    foreign_read = await async_client.patch(
        f"/v1/notifications/{foreign_id}/read",
        headers={"X-CSRF-Token": login["csrfToken"]},
    )
    assert first_read.status_code == 200
    assert repeated_read.status_code == 200
    assert repeated_read.json()["readAt"] == first_read.json()["readAt"]
    assert foreign_read.status_code == 404

    unread_only = await async_client.get("/v1/notifications", params={"unreadOnly": "true"})
    assert unread_only.status_code == 200
    assert {item["id"] for item in unread_only.json()["items"]} == {str(middle_id), str(oldest_id)}
    assert unread_only.json()["unreadCount"] == 2

    bulk = await async_client.post(
        "/v1/notifications/read-all",
        headers={"X-CSRF-Token": login["csrfToken"]},
    )
    repeated_bulk = await async_client.post(
        "/v1/notifications/read-all",
        headers={"X-CSRF-Token": login["csrfToken"]},
    )
    assert bulk.status_code == 200
    assert bulk.json() == {"updatedCount": 2, "unreadCount": 0}
    assert repeated_bulk.json() == {"updatedCount": 0, "unreadCount": 0}

    async with postgres_engine.connect() as connection:
        timestamps = (
            (
                await connection.execute(
                    text("SELECT read_at FROM notifications WHERE id IN (:middle_id, :oldest_id) ORDER BY id"),
                    {"middle_id": middle_id, "oldest_id": oldest_id},
                )
            )
            .scalars()
            .all()
        )
    assert len(timestamps) == 2
    assert timestamps[0] == timestamps[1]
