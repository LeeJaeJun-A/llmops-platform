.PHONY: help install dev run test lint format

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# === Development ===

install: ## Install dependencies
	pip install -e .

dev: ## Install with dev dependencies
	pip install -e ".[dev]"

run: ## Run the FastAPI server (requires local DB + Redis)
	uvicorn llmops.main:app --host 0.0.0.0 --port 8000 --reload

test: ## Run tests
	pytest -v --cov=llmops --cov-report=term-missing -m "not integration"

test-integration: ## Run integration tests (requires running DB + Redis)
	pytest -v tests/integration/ -m integration

lint: ## Run linter
	ruff check src/ tests/
	mypy src/

format: ## Format code
	ruff format src/ tests/
	ruff check --fix src/ tests/

# === Local (Docker Compose) ===

local-deploy: ## One-click local deploy
	./scripts/local/deploy.sh

local-down: ## Stop local services (keep data)
	./scripts/local/teardown.sh --keep-data

local-teardown: ## Stop local + remove all data
	./scripts/local/teardown.sh

local-logs: ## Follow local logs
	docker compose logs -f

# === Cloud (AWS EKS) ===

cloud-deploy: ## One-click AWS deploy
	./scripts/cloud/deploy.sh

cloud-teardown: ## Teardown all AWS resources
	./scripts/cloud/teardown.sh

cloud-status: ## Show AWS deployment status
	@echo "EKS:" && aws eks describe-cluster --name llmops-dev --region ap-northeast-2 --query "cluster.status" --output text 2>/dev/null || echo "  not found"
	@echo "Nodes:" && kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ' || echo "  0"
	@echo "Pods:" && kubectl get pods --no-headers 2>/dev/null | wc -l | tr -d ' ' || echo "  0"

# === Secrets ===

upload-secrets: ## Upload .env.secrets to AWS Secrets Manager
	./scripts/shared/upload-secrets.sh
