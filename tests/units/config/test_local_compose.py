"""Raw-text assertions over docker-compose.local.yml — deliberately no PyYAML dependency."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_COMPOSE_FILE = REPO_ROOT / "docker-compose.local.yml"


def test_local_compose_runs_a_one_shot_db_migrate_service():
    compose = LOCAL_COMPOSE_FILE.read_text()

    assert "db-migrate:" in compose
    assert 'command: sh -c "uv run alembic upgrade head"' in compose
    assert 'restart: "no"' in compose


def test_local_api_no_longer_runs_migrations_inline_and_waits_for_db_migrate():
    compose = LOCAL_COMPOSE_FILE.read_text()

    assert "alembic upgrade head && uv run uvicorn" not in compose
    assert 'command: sh -c "uv run uvicorn app:app' in compose

    lines = compose.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == "api:")
    indent = len(lines[start]) - len(lines[start].lstrip(" "))
    end = next(
        index
        for index, line in enumerate(lines)
        if index > start and line.strip() and (len(line) - len(line.lstrip(" "))) <= indent
    )
    api_block = "\n".join(lines[start:end])

    assert "db-migrate:" in api_block
    assert "condition: service_completed_successfully" in api_block


def test_local_compose_runs_an_email_worker_service_against_mailpit():
    compose = LOCAL_COMPOSE_FILE.read_text()

    lines = compose.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == "email-worker:")
    indent = len(lines[start]) - len(lines[start].lstrip(" "))
    end = next(
        index
        for index, line in enumerate(lines)
        if index > start and line.strip() and (len(line) - len(line.lstrip(" "))) <= indent
    )
    email_worker_block = "\n".join(lines[start:end])

    assert 'command: sh -c "uv run python worker.py"' in email_worker_block
    assert "SMTP_SERVER=mailpit" in email_worker_block
    assert "db-migrate:" in email_worker_block
    assert "condition: service_completed_successfully" in email_worker_block
    assert "postgres:" in email_worker_block
