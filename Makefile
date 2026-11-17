# Single entry point for local work (ADR 0010). Run `make help` for the list.
-include .env

IPHI_DB_USER ?= iphi
IPHI_DB_PASSWORD ?= iphi_local_dev
IPHI_DB_PORT ?= 5433
IPHI_API_PORT ?= 8000
IPHI_FRONTEND_PORT ?= 8080
IPHI_TEST_DATABASE_URL ?= postgresql+psycopg://$(IPHI_DB_USER):$(IPHI_DB_PASSWORD)@127.0.0.1:$(IPHI_DB_PORT)/postgres
export IPHI_TEST_DATABASE_URL

# Separate Compose project: own volume and ports, the development stack is never touched.
IPHI_DEMO_FRONTEND_PORT ?= 8081
IPHI_DEMO_API_PORT ?= 8001
IPHI_DEMO_DB_PORT ?= 5434
DEMO_URL := http://127.0.0.1:$(IPHI_DEMO_FRONTEND_PORT)
READY_URL ?= $(DEMO_URL)
# Extra arguments of scripts.demo, e.g. DEMO_ARGS=--no-live-incident
DEMO_ARGS ?=
DEMO_COMPOSE := IPHI_FRONTEND_PORT=$(IPHI_DEMO_FRONTEND_PORT) IPHI_API_PORT=$(IPHI_DEMO_API_PORT) \
	IPHI_DB_PORT=$(IPHI_DEMO_DB_PORT) docker compose -p iphi-demo

BACKEND := cd backend &&
FRONTEND := cd frontend &&

.DEFAULT_GOAL := help
.PHONY: help up down logs db install lint typecheck test test-backend test-frontend test-e2e \
	api-client api-drift check demo demo-up demo-running demo-down perf screenshots wait-ready

help: ## List targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

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

test-e2e: demo-running ## Playwright on the demo stack (started clean if not running): mandatory scenarios
	$(FRONTEND) IPHI_E2E_URL=$(DEMO_URL) pnpm test:e2e

api-client: ## Regenerate openapi.json and the typed frontend client
	$(BACKEND) uv run python -m scripts.export_openapi ../frontend/openapi.json
	$(FRONTEND) pnpm gen:api

API_CLIENT_FILES := frontend/openapi.json frontend/src/shared/api/schema.d.ts

api-drift: api-client ## Fail if the committed API client differs from the backend contract
	@test -z "$$(git status --porcelain -- $(API_CLIENT_FILES))" || \
		{ git status --short -- $(API_CLIENT_FILES); git diff -- $(API_CLIENT_FILES); \
		  echo "API client out of date or uncommitted: run make api-client and commit."; exit 1; }

check: lint typecheck test api-drift ## Everything CI runs, locally

wait-ready: ## Wait up to 3 min for READY_URL/ready (default: the demo stack)
	@for attempt in $$(seq 1 90); do \
		curl -fs -o /dev/null $(READY_URL)/ready && exit 0; sleep 2; \
	done; echo "$(READY_URL)/ready not ready after 180 s"; exit 1

demo-up: demo-down ## Start a clean, seeded demo stack (fresh volume) and wait until it is ready
	$(DEMO_COMPOSE) up --build -d
	@$(MAKE) --no-print-directory wait-ready || \
		{ $(DEMO_COMPOSE) ps --all; $(DEMO_COMPOSE) logs --tail 50; exit 1; }

demo-running: # Reuse a ready demo stack; every tool resets the simulation it needs
	@curl -fs -o /dev/null $(DEMO_URL)/ready || $(MAKE) --no-print-directory demo-up

demo: demo-up ## Scripted demonstration on a clean stack (docs/demo.md); leaves it running
	$(DEMO_COMPOSE) exec -T api python -m scripts.demo $(DEMO_ARGS)
	@echo "Interface $(DEMO_URL)  -  stop and remove with: make demo-down"

perf: demo-running ## Load test of the performance targets on the demo stack (PERF_ARGS="--history-days 7")
	$(DEMO_COMPOSE) exec -T api python -m scripts.perf $(PERF_ARGS)

screenshots: demo-running ## Regenerate the README screenshots from the demo stack (light and dark)
	$(FRONTEND) IPHI_E2E_URL=$(DEMO_URL) pnpm screenshots

demo-down: ## Stop the demo stack and delete its volume
	$(DEMO_COMPOSE) down --volumes --remove-orphans
