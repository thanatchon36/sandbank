.PHONY: install test lint typecheck check reproduce paper docs arxiv

install:
	uv sync --all-extras

test:
	uv run pytest --cov=sandbank --cov-report=term-missing

lint:
	uv run ruff check . && uv run ruff format --check .
	uv run mypy
	uv run python scripts/check_numbers.py

typecheck:
	uv run mypy

check: lint typecheck test

# Rebuild every figure and table from cached results/ — no model calls.
reproduce:
	uv run sandbank analyze

# The paper from cached results: numbers, tables and figures, the PDF and the executive brief, then the web version
# (docs/paper/, needs pandoc). No model calls.
paper: reproduce
	uv run python scripts/check_numbers.py
	cd paper && tectonic -X compile main.tex
	cd paper && tectonic -X compile brief.tex
	uv run python scripts/web_paper.py

# The documentation site (site/), with the web paper at /paper/.
docs: paper
	uv run --group docs mkdocs build --strict

# arXiv source bundle (paper/arxiv.tar.gz) plus the title, abstract and comments for the form.
arxiv: paper
	uv run python scripts/arxiv_bundle.py
