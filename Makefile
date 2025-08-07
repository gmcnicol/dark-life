.PHONY: init sync run

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

run:
	uv run run_pipeline.py
