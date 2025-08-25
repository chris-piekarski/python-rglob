.PHONY: lint

lint:
	@echo "Running pylint on package, setup, and tests..."
	pylint rglob setup.py features

.PHONY: dev-setup

dev-setup:
	@echo "Installing dev dependencies (pylint, behave)..."
	pip install -r requirements-dev.txt
