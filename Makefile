# Purpose: short aliases for the single supported deployment and test workflow.
.PHONY: install test lint build up down
install:
	uv sync --frozen
	cd frontend && npm ci
test:
	uv run pytest -q
lint:
	uv run ruff check backend common node_simulator migrations scripts tests research
	cd frontend && npm run lint
build:
	docker compose build
up:
	docker compose up -d --wait backend correlation explanations frontend
down:
	docker compose down
