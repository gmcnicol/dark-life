.PHONY: init sync test up all-up down logs api web renderer renderer-logs renderer-run renderer-ffreport renderer-clean scheduler scheduler-logs publisher publisher-logs ingest rebuild migrate smoke youtube-token

VENV_DIR := .venv
COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml

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
	$(COMPOSE) --profile renderer --profile publisher up -d --build postgres redis api web renderer publisher

all-up:
	$(COMPOSE) --profile renderer --profile publisher --profile scheduler up -d --build postgres redis api web renderer publisher scheduler

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

api:
	$(COMPOSE) up api

web:
	$(COMPOSE) up web

renderer:
	$(COMPOSE) up -d renderer

renderer-logs:
	$(COMPOSE) logs -f --tail=0 renderer

renderer-run:
	$(COMPOSE) run --rm --no-deps renderer python -u services/renderer/poller.py

renderer-ffreport:
	$(COMPOSE) run --rm --no-deps renderer sh -lc 'tail -F /tmp/ffreport-$$JOB.log'

renderer-clean:
	$(COMPOSE) run --rm --no-deps renderer rm -rf /tmp/renderer/* /tmp/ffreport-*.log

scheduler:
	$(COMPOSE) --profile scheduler up -d scheduler

scheduler-logs:
	$(COMPOSE) logs -f --tail=0 scheduler

publisher:
	$(COMPOSE) up -d publisher

publisher-logs:
	$(COMPOSE) logs -f --tail=0 publisher

ingest:
	$(COMPOSE) --profile ops run --rm reddit_ingestor incremental

rebuild:
	$(COMPOSE) build --no-cache

migrate:
	$(COMPOSE) build api
	$(COMPOSE) run --rm api sh -lc 'cd /app && alembic -c /app/alembic.ini upgrade head'

smoke:
	API_BASE=http://localhost:8000 python scripts/smoke_e2e.py

youtube-token:
	uv run python token_gen.py
