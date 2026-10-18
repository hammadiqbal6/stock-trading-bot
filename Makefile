.PHONY: help install install-dev lint typecheck test test-unit test-integration test-e2e \
	cov backtest validate run api docker-up docker-down pre-commit clean sample-validation

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

install: ## Install package
	pip install -e .

install-dev: ## Install package + dev/e2e extras
	pip install -e ".[dev,e2e]"
	pre-commit install || true
	playwright install chromium || true

lint: ## Run ruff linter
	ruff check trading_bot tests
	ruff format --check trading_bot tests

format: ## Auto-format with ruff
	ruff check --fix trading_bot tests
	ruff format trading_bot tests

typecheck: ## Run mypy
	mypy trading_bot

test: ## Run unit + integration tests
	pytest tests/unit tests/integration -q --cov=trading_bot --cov-report=term-missing --cov-report=xml

test-unit: ## Unit tests only
	pytest tests/unit -q

test-integration: ## Integration tests (mocked externals)
	pytest tests/integration -q

test-e2e: ## Playwright UI tests
	pytest tests/e2e -q --browser chromium --no-cov

cov: ## Coverage report
	pytest tests/unit tests/integration --cov=trading_bot --cov-report=term-missing --cov-report=html

backtest: ## Run sample backtest
	python -m trading_bot.cli backtest --config config/settings.yaml

validate: ## Run walk-forward validation report
	python -m trading_bot.cli validate --config config/settings.yaml

sample-validation: ## Quick sample validation with public data
	python scripts/run_sample_validation.py

run: ## Run trading loop once (paper)
	python -m trading_bot.cli run --once

api: ## Start dashboard API + UI
	uvicorn trading_bot.api.app:app --host 0.0.0.0 --port 8000 --reload

docker-up: ## Start stack via docker-compose
	docker compose up --build -d

docker-down: ## Stop docker stack
	docker compose down

pre-commit: ## Run pre-commit on all files
	pre-commit run --all-files

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
