# RTC Backend - Development Makefile

.PHONY: help install dev test lint format clean run init-db

help: ## Show this help message
	@echo "RTC Backend - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -e .

install-vectors: ## Install with vector support
	pip install -e ".[vectors]"

install-dev: ## Install with dev dependencies
	pip install -e ".[vectors]"
	pip install pytest pytest-asyncio ruff mypy

init-db: ## Initialize database
	python -c "from app.db.sqlite import init_db; init_db()"

reset-db: ## Reset database (DESTRUCTIVE!)
	@echo "⚠️  This will delete all data!"
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	python -c "from app.db.sqlite import init_db; init_db(drop_all=True)"

dev: ## Run development server
	uvicorn app.main:app --reload --port 8000

run: ## Run production server
	uvicorn app.main:app --host 0.0.0.0 --port 8000

test: ## Run tests
	pytest -v

test-cov: ## Run tests with coverage
	pytest --cov=app --cov-report=html --cov-report=term

lint: ## Check code with ruff
	ruff check app/

format: ## Format code with ruff
	ruff format app/
	ruff check app/ --fix

typecheck: ## Type check with mypy
	mypy app/ --ignore-missing-imports

clean: ## Clean up generated files
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

check: lint typecheck test ## Run all checks

# === Job Triggers ===

ingest: ## Trigger ingestion job
	curl -X POST http://localhost:8000/ingest/run \
	  -H "Content-Type: application/json" \
	  -d '{"max_results": 20}'

insights: ## Generate insights
	curl -X POST http://localhost:8000/jobs/generate-insights

hypotheses: ## Generate hypotheses
	curl -X POST http://localhost:8000/jobs/generate-hypotheses

refresh-vectors: ## Refresh vector embeddings
	curl -X POST http://localhost:8000/jobs/refresh-vectors

health: ## Check health
	curl http://localhost:8000/health | python -m json.tool

# === Docker ===

docker-build: ## Build Docker image
	docker build -t rtc-backend:latest .

docker-run: ## Run Docker container
	docker run -p 8000:8000 --env-file .env rtc-backend:latest

# === Deployment ===

deploy-check: ## Pre-deployment checks
	@echo "Running pre-deployment checks..."
	@echo "✓ Checking dependencies..."
	@pip list | grep -E "fastapi|uvicorn|sqlmodel"
	@echo "✓ Running tests..."
	@pytest -q
	@echo "✓ Checking lints..."
	@ruff check app/
	@echo "✅ All checks passed!"

