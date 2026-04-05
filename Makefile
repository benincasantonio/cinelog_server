.PHONY: install dev hooks test-unit test-e2e lint format typecheck security dependency-audit run docker-up docker-down docker-build-prod docker-prod-up docker-prod-down migrate migrate-dry-run

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
	docker compose -f docker-compose.e2e.yml up -d
	uv run pytest tests/e2e/ -v; status=$$?; docker compose -f docker-compose.e2e.yml down; exit $$status

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

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
