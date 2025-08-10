.PHONY: init sync test run-webapp renderer uploader run-renderer run-uploader up down smoke

VENV_DIR := .venv

init:
	@command -v uv >/dev/null 2>&1 || { \
	    echo "uv is required but not installed. See https://github.com/astral-sh/uv"; \
	    exit 1; \
	}
	@[ -d $(VENV_DIR) ] || uv venv $(VENV_DIR)
	uv sync
	@echo "Virtual environment ready. Activate with: . $(VENV_DIR)/bin/activate"

sync:
	uv sync

run-webapp:
	uv run python -m webapp.main run

renderer:
	uv run python -m video_renderer.render_job_runner run

uploader:
	uv run python -m video_uploader.cron_upload run

run-renderer: renderer

run-uploader: uploader

up:
	docker compose -f infra/docker-compose.yml up

down:
	docker compose -f infra/docker-compose.yml down

smoke:
	python scripts/smoke_e2e.py

test:
	uv run --with pytest,httpx pytest -q
