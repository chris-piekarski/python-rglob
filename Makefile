.PHONY: lint

lint:
	@echo "Running pylint on package, setup, and tests..."
	pylint rglob setup.py features

