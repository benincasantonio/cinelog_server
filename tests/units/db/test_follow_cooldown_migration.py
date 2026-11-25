"""The cooldown index preserves history and supports upgrade/downgrade."""

from tests.alembic_test_harness import AlembicTestHarness

PREVIOUS_REVISION = "010_create_movie_providers_table"
REVISION = "011_add_follow_cooldown_index"


def test_follow_cooldown_index_preserves_history(alembic_test_harness: AlembicTestHarness):
    harness = alembic_test_harness
    harness.upgrade(PREVIOUS_REVISION)
    with harness.connect() as connection:
        user_id = connection.execute(
            """INSERT INTO users (email, handle, first_name, last_name)
               VALUES ('cooldown@example.com', 'cooldown', 'Cool', 'Down') RETURNING id"""
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO notifications (recipient_id, actor_id, type, title, body, deleted, deduplication_key)
               VALUES (%s, %s, 'follow.started', 'Title', 'Body', TRUE, 'legacy-week')""",
            (user_id, user_id),
        )
        original = connection.execute("SELECT * FROM notifications").fetchall()

    harness.upgrade(REVISION)
    with harness.connect() as connection:
        index = connection.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_notifications_follow_started_cooldown'"
        ).fetchone()[0]
        assert "(recipient_id, actor_id, created_at DESC)" in index
        assert "type = 'follow.started'" in index
        assert "deleted" not in index
        assert connection.execute("SELECT * FROM notifications").fetchall() == original

    harness.downgrade(PREVIOUS_REVISION)
    with harness.connect() as connection:
        assert connection.execute("SELECT to_regclass('ix_notifications_follow_started_cooldown')").fetchone() == (
            None,
        )
        assert connection.execute("SELECT * FROM notifications").fetchall() == original
    harness.upgrade(REVISION)
