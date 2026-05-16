.PHONY: help setup dev test lint format ingest dashboard db-up db-down migrate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Create virtual environment and install dependencies
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

dev: ## Install in development mode
	.venv/bin/pip install -e ".[dev]"

test: ## Run tests
	.venv/bin/python -m pytest tests/ -v --tb=short

lint: ## Run linter
	.venv/bin/ruff check app/ tests/

format: ## Format code
	.venv/bin/ruff format app/ tests/

db-up: ## Start PostgreSQL container
	docker compose up -d db

db-down: ## Stop PostgreSQL container
	docker compose down

migrate: ## Run database migrations
	.venv/bin/alembic upgrade head

ingest: ## Run CRZ data ingestion
	.venv/bin/python -m app.ingestion.jobs

dashboard: ## Start Streamlit dashboard
	.venv/bin/streamlit run app/dashboard/Home.py --server.port 8501
