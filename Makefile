# Single entry point for local work (ADR 0010). Run `make help` for the list.
-include .env

IPHI_DB_USER ?= iphi
IPHI_DB_PASSWORD ?= iphi_local_dev
IPHI_DB_PORT ?= 5433
IPHI_API_PORT ?= 8000
IPHI_FRONTEND_PORT ?= 8080
IPHI_TEST_DATABASE_URL ?= postgresql+psycopg://$(IPHI_DB_USER):$(IPHI_DB_PASSWORD)@127.0.0.1:$(IPHI_DB_PORT)/postgres
export IPHI_TEST_DATABASE_URL

BACKEND := cd backend &&
FRONTEND := cd frontend &&

.DEFAULT_GOAL := help
.PHONY: help up down logs db install lint typecheck test test-backend test-frontend \
	api-client api-drift check demo

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

up: ## Build and start the whole stack (db, migrate, api, worker, frontend)
	docker compose up --build -d
	@echo "Frontend http://127.0.0.1:$(IPHI_FRONTEND_PORT)  API docs http://127.0.0.1:$(IPHI_API_PORT)/docs"

down: ## Stop the stack (data volume kept)
	docker compose down

logs: ## Follow the logs of every service
	docker compose logs -f

db: ## Start PostgreSQL only and wait until it is healthy
	docker compose up -d --wait db

install: ## Install backend and frontend dependencies from the lockfiles
	$(BACKEND) uv sync --locked
	$(FRONTEND) pnpm install --frozen-lockfile

lint: ## Ruff, import contracts, ESLint, Prettier
	$(BACKEND) uv run ruff format --check . && uv run ruff check . && uv run lint-imports
	$(FRONTEND) pnpm lint

typecheck: ## mypy --strict and tsc
	$(BACKEND) uv run mypy
	$(FRONTEND) pnpm typecheck

test-backend: db ## Backend unit + integration tests against PostgreSQL
	$(BACKEND) uv run pytest --cov --cov-report=term-missing:skip-covered

test-frontend: ## Vitest (components, accessibility)
	$(FRONTEND) pnpm test

test: test-backend test-frontend ## All automated tests

api-client: ## Regenerate openapi.json and the typed frontend client
	$(BACKEND) uv run python -m scripts.export_openapi ../frontend/openapi.json
	$(FRONTEND) pnpm gen:api

API_CLIENT_FILES := frontend/openapi.json frontend/src/shared/api/schema.d.ts

api-drift: api-client ## Fail if the committed API client differs from the backend contract
	@test -z "$$(git status --porcelain -- $(API_CLIENT_FILES))" || \
		{ git status --short -- $(API_CLIENT_FILES); git diff -- $(API_CLIENT_FILES); \
		  echo "API client out of date or uncommitted: run make api-client and commit."; exit 1; }

check: lint typecheck test api-drift ## Everything CI runs, locally

demo: ## Stub until US-10: starts the stack; scripted scenarios arrive with US-02 and US-10
	@echo "make demo is a stub until US-10 (docs/03-backlog.md); starting the stack instead."
	@$(MAKE) --no-print-directory up
