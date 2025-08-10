.PHONY: init sync test up down logs renderer uploader ingest backfill rebuild smoke

VENV_DIR := .venv
COMPOSE := docker compose -f infra/docker-compose.yml

init:
	command -v uv >/dev/null 2>&1 || { echo "uv is required but not installed. See https://github.com/astral-sh/uv"; exit 1; }
	[ -d $(VENV_DIR) ] || uv venv $(VENV_DIR)
	uv sync
	@echo "Virtual environment ready. Activate with: . $(VENV_DIR)/bin/activate"

sync:
	uv sync

test:
	uv run --with pytest,httpx pytest -q

up:
	$(COMPOSE) up -d postgres redis api web

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

renderer:
	$(COMPOSE) up -d renderer

uploader:
	$(COMPOSE) run --rm uploader

ingest:
	$(COMPOSE) --profile ops run --rm reddit_ingestor incremental

backfill:
	$(COMPOSE) --profile ops run --rm reddit_ingestor backfill

rebuild:
	$(COMPOSE) build --no-cache

smoke:
	python scripts/smoke_e2e.py
