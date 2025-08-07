.PHONY: sync run

sync:
	uv sync

run:
	uv run run_pipeline.py
