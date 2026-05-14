.DEFAULT_GOAL := help

# Auto-prefer the project's virtualenv when one exists. Falls back to
# `python3` on PATH so CI (which runs without `.venv/`) still works.
PYTHON ?= $(if $(wildcard .venv/bin/python),$(CURDIR)/.venv/bin/python,python3)
PACKAGE := rglob

.PHONY: help build lint test fmt docs docs-build dev-setup clean

help:  ## Show this help menu
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build:  ## Build sdist + wheel into dist/ (uses hatch)
	$(PYTHON) -m hatch build

lint:  ## Run ruff + mypy --strict (gating)
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m mypy --strict src/$(PACKAGE)

test:  ## Run pytest with coverage + behave (gating; local 100% coverage)
	$(PYTHON) -m pytest --cov=$(PACKAGE) --cov-branch --cov-report=term-missing --cov-fail-under=100
	$(PYTHON) -m behave

fmt:  ## Auto-format with ruff (modifies files in place)
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

docs:  ## Serve MkDocs preview on http://localhost:8000
	$(PYTHON) -m mkdocs serve

docs-build:  ## Build static docs site to ./site
	$(PYTHON) -m mkdocs build --strict

dev-setup:  ## Install dev extras + pre-commit hooks
	$(PYTHON) -m pip install -e ".[dev,bdd,docs,gitignore,ext,bench]"
	$(PYTHON) -m pre_commit install

clean:  ## Remove caches, build artefacts, coverage outputs, docs site
	rm -rf dist build site \
		.pytest_cache .mypy_cache .ruff_cache htmlcov \
		.coverage .coverage.* coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
