# Makefile for Podcast Transcriber Testing

# Variables
PYTHON := python3
VENV := venv
PYTEST := $(VENV)/bin/pytest
PIP := $(VENV)/bin/pip
COVERAGE := $(VENV)/bin/coverage

# Default target
.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: test
test: ## Run all tests quickly
	@echo "Running tests..."
	@$(PYTEST)

.PHONY: test-unit
test-unit: ## Run only unit tests
	@echo "Running unit tests..."
	@$(PYTEST) -m unit

.PHONY: test-integration
test-integration: ## Run only integration tests
	@echo "Running integration tests..."
	@$(PYTEST) -m integration

.PHONY: test-fast
test-fast: ## Run tests excluding slow ones
	@echo "Running fast tests..."
	@$(PYTEST) -m "not slow"

.PHONY: test-verbose
test-verbose: ## Run tests with verbose output
	@echo "Running tests with verbose output..."
	@$(PYTEST) -vv

.PHONY: test-parallel
test-parallel: ## Run tests in parallel (requires pytest-xdist)
	@echo "Running tests in parallel..."
	@$(PYTEST) -n auto

.PHONY: coverage
coverage: ## Run tests with coverage report
	@echo "Running tests with coverage..."
	@$(COVERAGE) run -m pytest
	@$(COVERAGE) report
	@$(COVERAGE) html
	@echo "Coverage report generated in htmlcov/"

.PHONY: coverage-report
coverage-report: ## Show coverage report in terminal
	@$(COVERAGE) report

.PHONY: coverage-html
coverage-html: ## Open HTML coverage report
	@open htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html 2>/dev/null || echo "Please open htmlcov/index.html manually"

.PHONY: test-failed
test-failed: ## Re-run only failed tests
	@echo "Re-running failed tests..."
	@$(PYTEST) --lf

.PHONY: test-watch
test-watch: ## Run tests in watch mode (requires pytest-watch)
	@echo "Running tests in watch mode..."
	@$(VENV)/bin/ptw

.PHONY: clean-test
clean-test: ## Remove test artifacts
	@echo "Cleaning test artifacts..."
	@rm -rf .pytest_cache
	@rm -rf .coverage
	@rm -rf htmlcov
	@rm -rf .tox
	@rm -f tests.log
	@rm -f coverage.xml
	@rm -f coverage.json
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete

.PHONY: install-test-deps
install-test-deps: ## Install test dependencies
	@echo "Installing test dependencies..."
	@$(PIP) install pytest pytest-asyncio pytest-mock pytest-cov pytest-timeout

.PHONY: lint
lint: ## Run linting checks
	@echo "Running linting checks..."
	@$(VENV)/bin/flake8 src tests --max-line-length=100 --ignore=E203,W503
	@$(VENV)/bin/black --check src tests
	@$(VENV)/bin/isort --check-only src tests

.PHONY: format
format: ## Format code
	@echo "Formatting code..."
	@$(VENV)/bin/black src tests
	@$(VENV)/bin/isort src tests

.PHONY: type-check
type-check: ## Run type checking with mypy
	@echo "Running type checks..."
	@$(VENV)/bin/mypy src --ignore-missing-imports

.PHONY: test-all
test-all: clean-test lint type-check test coverage ## Run all checks and tests

.PHONY: test-ci
test-ci: ## Run tests suitable for CI environment
	@echo "Running CI tests..."
	@$(PYTEST) --junit-xml=test-results.xml --cov-report=xml

.PHONY: test-debug
test-debug: ## Run tests with debugging enabled
	@echo "Running tests with debugging..."
	@$(PYTEST) -vv --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb

.PHONY: test-markers
test-markers: ## Show all available test markers
	@echo "Available test markers:"
	@$(PYTEST) --markers

.PHONY: test-collect
test-collect: ## Show which tests would be collected
	@echo "Collecting tests..."
	@$(PYTEST) --collect-only -q