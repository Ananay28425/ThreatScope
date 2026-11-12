.PHONY: install test lint build demo
install:
	uv sync --frozen
	npm --prefix frontend ci
test:
	uv run pytest -q
lint:
	uv run ruff check backend common node_simulator migrations scripts tests research
	npm --prefix frontend run lint
build:
	npm --prefix frontend run build
demo:
	uv run --frozen python -m scripts.demo
