.DEFAULT_GOAL := help

UV ?= uv
NPM ?= npm
DOCKER ?= docker
IMAGE ?= docker.io/tronton/taskqueue
TAG ?= latest
COMPOSE = $(DOCKER) compose

.PHONY: help setup setup-backend setup-frontend dev dev-backend dev-frontend build serve test image publish up down restart logs status config health init-deploy

help:
	@printf '%s\n' \
	  'Task Queue — run from the repository root' \
	  '' \
	  '  make setup          Install locked Python and frontend dependencies' \
	  '  make dev            Run backend (:8080) and Vite (:5173); Ctrl+C stops both' \
	  '  make dev-backend    Run FastAPI + MCP with reload' \
	  '  make dev-frontend   Run Vite with the API proxy' \
	  '  make build          Compile the frontend' \
	  '  make serve          Serve the compiled frontend, REST and MCP on :8080' \
	  '  make test           Run backend and MCP tests' \
	  '  make image          Build the fullstack Docker image' \
	  '  make publish        Build and push docker.io/tronton/taskqueue (TAG=latest)' \
	  '  make up             Start Compose from published images in the background' \
	  '  make down           Stop Compose and preserve the SQLite volume' \
	  '  make restart        Restart the Compose service' \
	  '  make logs           Follow service logs' \
	  '  make status         Show Compose service status' \
	  '  make config         Validate and show resolved Compose configuration' \
	  '  make health         Check the running backend container' \
	  '  make init-deploy    Generate deployment secrets (run with sudo)'

setup: setup-backend setup-frontend

setup-backend:
	$(UV) sync --frozen

setup-frontend:
	$(NPM) --prefix webui ci

dev:
	$(MAKE) --jobs=2 dev-backend dev-frontend

dev-backend:
	$(UV) run --frozen uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload

dev-frontend:
	$(NPM) --prefix webui run dev

build:
	$(NPM) --prefix webui run build

serve: build
	$(UV) run --frozen uvicorn backend.main:app --host 0.0.0.0 --port 8080

test:
	$(UV) run --frozen pytest backend

image:
	$(DOCKER) build --tag $(IMAGE):$(TAG) .

publish:
	$(DOCKER) build --tag $(IMAGE):$(TAG) .
	$(DOCKER) push $(IMAGE):$(TAG)

up:
	$(COMPOSE) up --detach

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart task-queue

logs:
	$(COMPOSE) logs --follow --tail=100 task-queue

status:
	$(COMPOSE) ps

config:
	$(COMPOSE) config

health:
	$(COMPOSE) exec -T task-queue python -m backend.healthcheck

init-deploy:
	python3 scripts/init-deploy.py
