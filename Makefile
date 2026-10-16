.PHONY: install test lint typecheck check reproduce

install:
	uv sync --all-extras

test:
	uv run pytest --cov=sandbank --cov-report=term-missing

lint:
	uv run ruff check . && uv run ruff format --check .

typecheck:
	uv run mypy

check: lint typecheck test

# Rebuild every figure and table from cached results/ — no model calls.
reproduce:
	uv run sandbank analyze
