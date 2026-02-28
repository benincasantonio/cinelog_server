.PHONY: install dev test-unit test-e2e lint format typecheck security run docker-up docker-down

install:
	uv sync

dev:
	uv sync --group dev

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
	uv run bandit -r app/

run:
	uv run python main.py

docker-up:
	docker compose -f docker-compose.local.yml up --build

docker-down:
	docker compose -f docker-compose.local.yml down
