from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROD_COMPOSE_FILE = REPO_ROOT / "docker-compose.prod.yml"


def test_prod_compose_runs_schema_migration_job():
    compose = PROD_COMPOSE_FILE.read_text()

    assert "db-migrate:" in compose
    assert "alembic" in compose
    assert "upgrade" in compose
    assert "db_migrations" not in compose


def test_prod_api_waits_for_successful_migration_job():
    compose = PROD_COMPOSE_FILE.read_text()

    assert "db-migrate:" in compose
    assert "condition: service_completed_successfully" in compose
    assert "DATABASE_URL: ${DATABASE_URL:?Set DATABASE_URL to the external PostgreSQL database}" in compose
    assert "MONGODB_URI" not in compose
    assert "DB_BACKEND" not in compose
    assert "image: postgres" not in compose
    assert "postgres_data:" not in compose


def test_prod_compose_runs_email_worker_service():
    compose = PROD_COMPOSE_FILE.read_text()

    assert "email-worker:" in compose
    assert 'command: ["python", "worker.py"]' in compose


def test_prod_email_worker_waits_for_migration_and_disables_the_http_healthcheck():
    compose = PROD_COMPOSE_FILE.read_text()

    lines = compose.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == "email-worker:")
    indent = len(lines[start]) - len(lines[start].lstrip(" "))
    end = next(
        index
        for index, line in enumerate(lines)
        if index > start and line.strip() and (len(line) - len(line.lstrip(" "))) <= indent
    )
    email_worker_block = "\n".join(lines[start:end])

    assert "<<: *app-env" in email_worker_block
    assert "Dockerfile.prod" in email_worker_block
    assert "db-migrate:" in email_worker_block
    assert "condition: service_completed_successfully" in email_worker_block
    assert "healthcheck:" in email_worker_block
    assert "disable: true" in email_worker_block
    assert "restart: unless-stopped" in email_worker_block
