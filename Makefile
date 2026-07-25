.PHONY: install dev hooks test-unit test-e2e lint format format-check typecheck security dependency-audit run run-email-worker docker-up docker-down docker-build-prod docker-prod-up docker-prod-down db-schema-migrate db-schema-migrate-dry-run db-schema-rollback

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
	status=0; \
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
		REGISTRATION_VERIFICATION_HMAC_SECRET=test-registration-verification-hmac-secret \
		CURSOR_PAGINATION_HMAC_SECRET=test-cursor-pagination-hmac-secret \
		DATABASE_URL=postgresql+asyncpg://cinelog:cinelog@localhost:5433/cinelog_e2e_db \
		uv run alembic upgrade head; \
		status=$$?; \
	fi; \
	if [ "$$status" -eq 0 ]; then \
		JWT_SECRET_KEY=test-jwt-secret-key-for-e2e-1234567890 \
		RATE_LIMIT_HMAC_SECRET=test-rate-limit-hmac-secret \
		REGISTRATION_VERIFICATION_HMAC_SECRET=test-registration-verification-hmac-secret \
		CURSOR_PAGINATION_HMAC_SECRET=test-cursor-pagination-hmac-secret \
		DATABASE_URL=postgresql+asyncpg://cinelog:cinelog@localhost:5433/cinelog_e2e_db \
		uv run pytest tests/e2e/ -v; \
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

run-email-worker:
	uv run python worker.py

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

db-schema-migrate:
	uv run alembic upgrade head

db-schema-migrate-dry-run:
	uv run alembic upgrade head --sql

db-schema-rollback:
	uv run alembic downgrade -1
