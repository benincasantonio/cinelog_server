.PHONY: install dev hooks test-unit test-e2e lint format format-check typecheck security dependency-audit run docker-up docker-down docker-build-prod docker-prod-up docker-prod-down migrate migrate-dry-run db-data-migrate db-data-migrate-dry-run postgres-migrate-all postgres-migrate-all-dry-run migrate-all migrate-all-dry-run db-schema-migrate db-schema-migrate-dry-run db-schema-rollback

install:
	uv sync

dev:
	uv sync --group dev
	git config core.hooksPath .githooks

hooks:
	git config core.hooksPath .githooks

test-unit:
	uv run pytest tests/units/ --cov=app --cov-report=html

test-e2e:
	backend="$${E2E_BACKEND:-mongo}"; \
	status=0; \
	if [ "$$backend" = "postgres" ]; then \
		docker compose -f docker-compose.e2e.yml up -d redis_e2e postgres_e2e; \
		ready=0; \
		for i in $$(seq 1 30); do \
			if docker compose -f docker-compose.e2e.yml exec -T postgres_e2e pg_isready -U cinelog -d cinelog_e2e_db >/dev/null 2>&1; then \
				ready=1; \
				break; \
			fi; \
			sleep 1; \
		done; \
		if [ "$$ready" -ne 1 ]; then \
			status=1; \
		fi; \
		if [ "$$status" -eq 0 ]; then \
			JWT_SECRET_KEY=test-jwt-secret-key-for-e2e-1234567890 \
			RATE_LIMIT_HMAC_SECRET=test-rate-limit-hmac-secret \
			DATABASE_URL=postgresql+asyncpg://cinelog:cinelog@localhost:5433/cinelog_e2e_db \
			E2E_BACKEND=postgres \
			uv run alembic upgrade head; \
			status=$$?; \
		fi; \
		if [ "$$status" -eq 0 ]; then \
			JWT_SECRET_KEY=test-jwt-secret-key-for-e2e-1234567890 \
			RATE_LIMIT_HMAC_SECRET=test-rate-limit-hmac-secret \
			DATABASE_URL=postgresql+asyncpg://cinelog:cinelog@localhost:5433/cinelog_e2e_db \
			E2E_BACKEND=postgres \
			uv run pytest tests/e2e/ -v; \
			status=$$?; \
		fi; \
	else \
		docker compose -f docker-compose.e2e.yml up -d redis_e2e mongo_e2e; \
		JWT_SECRET_KEY=test-jwt-secret-key-for-e2e-1234567890 \
		RATE_LIMIT_HMAC_SECRET=test-rate-limit-hmac-secret \
		E2E_BACKEND=mongo uv run pytest tests/e2e/ -v; \
		status=$$?; \
	fi; \
	docker compose -f docker-compose.e2e.yml down; \
	exit $$status

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy app/

security:
	uv run bandit -r app/ -c pyproject.toml

dependency-audit:
	uv run pip-audit

run:
	uv run python main.py

docker-up:
	docker compose -f docker-compose.local.yml up --build -d

docker-down:
	docker compose -f docker-compose.local.yml down

docker-build-prod:
	docker compose -f docker-compose.prod.yml build

docker-prod-up:
	docker compose -f docker-compose.prod.yml up --build -d

docker-prod-down:
	docker compose -f docker-compose.prod.yml down

migrate:
	uv run python -m migrations.runner

migrate-dry-run:
	uv run python -m migrations.runner --dry-run

db-data-migrate:
	uv run python -m db_migrations.runner --yes

db-data-migrate-dry-run:
	uv run python -m db_migrations.runner --dry-run

postgres-migrate-all:
	uv run alembic upgrade head
	uv run python -m db_migrations.runner --yes

postgres-migrate-all-dry-run:
	uv run alembic upgrade head --sql
	uv run python -m db_migrations.runner --dry-run

migrate-all:
	uv run python -m migrations.runner --yes
	uv run alembic upgrade head
	uv run python -m db_migrations.runner --yes

migrate-all-dry-run:
	uv run python -m migrations.runner --dry-run
	uv run alembic upgrade head --sql
	uv run python -m db_migrations.runner --dry-run

db-schema-migrate:
	uv run alembic upgrade head

db-schema-migrate-dry-run:
	uv run alembic upgrade head --sql

db-schema-rollback:
	uv run alembic downgrade -1
