.RECIPEPREFIX := >
.PHONY: init sync test up down logs api web renderer renderer-logs renderer-run renderer-ffreport renderer-clean uploader ingest rebuild migrate smoke

VENV_DIR := .venv
COMPOSE := docker compose -f infra/docker-compose.yml

init:
>command -v uv >/dev/null 2>&1 || { echo "uv is required but not installed. See https://github.com/astral-sh/uv"; exit 1; }
>[ -d $(VENV_DIR) ] || uv venv $(VENV_DIR)
>uv sync
>@echo "Virtual environment ready. Activate with: . $(VENV_DIR)/bin/activate"

sync:
>uv sync

test:
>uv run --with pytest,httpx pytest -q

up:
>$(COMPOSE) up -d postgres redis api web

down:
>$(COMPOSE) down

logs:
>$(COMPOSE) logs -f

api:
>$(COMPOSE) up api

web:
>$(COMPOSE) up web

renderer:
>$(COMPOSE) up -d renderer

renderer-logs:
>$(COMPOSE) logs -f --tail=0 renderer

renderer-run:
>$(COMPOSE) run --rm --no-deps renderer \
    python -u video_renderer/create_slideshow.py \
    --job-id $$JOB --story-id $$STORY --part-id $$PART --frames-dir $$FRAMES --debug

renderer-ffreport:
>$(COMPOSE) run --rm --no-deps renderer sh -lc 'tail -F /tmp/ffreport-$$JOB.log'

renderer-clean:
>$(COMPOSE) run --rm --no-deps renderer rm -rf /tmp/renderer/* /tmp/ffreport-*.log

uploader:
>$(COMPOSE) run --rm uploader

ingest:
>$(COMPOSE) --profile ops run --rm reddit_ingestor incremental

rebuild:
>$(COMPOSE) build --no-cache

migrate:
>$(COMPOSE) run --rm api sh -lc 'cd apps/api && alembic -c ../../alembic.ini upgrade head'

smoke:
>API_BASE=http://localhost:8000 python scripts/smoke_e2e.py
