.DEFAULT_GOAL := help

PYTHON ?= python3
PACKAGE := rglob

.PHONY: help build lint test fmt docs docs-build dev-setup clean

help:  ## Show this help menu
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build:  ## Build sdist + wheel into dist/ (uses hatch)
	hatch build

lint:  ## Run ruff + mypy --strict (gating)
	ruff check .
	ruff format --check .
	mypy --strict src/$(PACKAGE)

test:  ## Run pytest with coverage + behave (gating; local 100% coverage)
	pytest --cov=$(PACKAGE) --cov-branch --cov-report=term-missing --cov-fail-under=100
	behave

fmt:  ## Auto-format with ruff (modifies files in place)
	ruff format .
	ruff check --fix .

docs:  ## Serve MkDocs preview on http://localhost:8000
	mkdocs serve

docs-build:  ## Build static docs site to ./site
	mkdocs build --strict

dev-setup:  ## Install dev extras + pre-commit hooks
	$(PYTHON) -m pip install -e ".[dev,bdd,docs,gitignore,ext,bench]"
	pre-commit install

clean:  ## Remove caches, build artefacts, coverage outputs, docs site
	rm -rf dist build site \
		.pytest_cache .mypy_cache .ruff_cache htmlcov \
		.coverage .coverage.* coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
