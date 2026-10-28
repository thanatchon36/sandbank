.PHONY: install test lint typecheck check reproduce paper arxiv

install:
	uv sync --all-extras

test:
	uv run pytest --cov=sandbank --cov-report=term-missing

lint:
	uv run ruff check . && uv run ruff format --check .
	uv run python scripts/check_numbers.py

typecheck:
	uv run mypy

check: lint typecheck test

# Rebuild every figure and table from cached results/ — no model calls.
reproduce:
	uv run sandbank analyze

# The paper from cached results: numbers, tables and figures, then the PDF (no model calls).
paper: reproduce
	uv run python scripts/check_numbers.py
	cd paper && tectonic -X compile main.tex

# arXiv source bundle (paper/arxiv.tar.gz) plus the title, abstract and comments for the form.
arxiv: paper
	uv run python scripts/arxiv_bundle.py
