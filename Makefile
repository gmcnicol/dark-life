.PHONY: init sync test run-webapp run-renderer run-uploader

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

run-renderer:
	uv run python -m video_renderer.render_job_runner run

run-uploader:
	uv run python -m video_uploader.cron_upload run

test:
	uv run --with pytest pytest -q
