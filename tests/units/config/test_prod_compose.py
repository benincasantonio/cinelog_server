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
