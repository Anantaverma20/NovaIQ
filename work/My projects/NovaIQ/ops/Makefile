.PHONY: help install dev up down logs clean test lint

help: ## Show this help message
	@echo "NovaIQ - Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies for backend and frontend
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

dev-backend: ## Run backend in development mode
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Run frontend in development mode
	cd frontend && npm run dev

dev: ## Run both backend and frontend (requires tmux or separate terminals)
	@echo "Run 'make dev-backend' in one terminal and 'make dev-frontend' in another"

up: ## Start all services with docker-compose
	cd ops && docker-compose up -d

down: ## Stop all services
	cd ops && docker-compose down

logs: ## Show docker-compose logs
	cd ops && docker-compose logs -f

clean: ## Clean up generated files and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	rm -f backend/novaiq.db backend/novaiq.db-* 2>/dev/null || true

test: ## Run backend tests
	cd backend && pytest tests/ -v

lint: ## Run linters
	cd backend && ruff check . && black --check .
	cd frontend && npm run lint

format: ## Format code
	cd backend && black . && ruff check --fix .
	cd frontend && npm run lint -- --fix

init-db: ## Initialize database
	cd backend && python -c "from app.db.sqlite import init_db; init_db()"

ingest: ## Trigger manual ingestion
	curl -X POST http://localhost:8000/ingest/run

health: ## Check backend health
	curl http://localhost:8000/health

