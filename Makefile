.PHONY: help setup dev test lint format ingest dashboard db-up db-down migrate backup backup-list backup-verify restore restore-test check-freshness

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

check-freshness: ## Check data freshness (exit 1 if stale)
	.venv/bin/python -m app.alerts.freshness_alert

backup: ## Run database backup (optional — all data re-downloadable from CRZ API)
	@bash scripts/backup.sh

backup-list: ## List available backups
	@ls -lh backups/crz_monitor_*.dump 2>/dev/null || echo "No backups found"

backup-verify: ## Verify latest backup
	@latest=$$(ls -t backups/crz_monitor_*.dump 2>/dev/null | head -1); \
	if [ -n "$$latest" ]; then \
		echo "Verifying: $$latest"; \
		docker exec -i crz_db pg_restore --list < "$$latest" 2>&1 | head -20; \
	else \
		echo "No backups found"; \
	fi

restore: ## Restore from backup (usage: make restore DUMP=backups/crz_monitor_20260517.dump)
	@if [ -z "$(DUMP)" ]; then echo "Usage: make restore DUMP=<path_to_dump>"; exit 1; fi
	@bash scripts/restore.sh --apply "$(DUMP)"

restore-test: ## Test-restore a backup (usage: make restore-test DUMP=backups/crz_monitor_20260517.dump)
	@if [ -z "$(DUMP)" ]; then echo "Usage: make restore-test DUMP=<path_to_dump>"; exit 1; fi
	@bash scripts/restore.sh --test "$(DUMP)"
