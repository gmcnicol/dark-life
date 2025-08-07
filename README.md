# dark-life

Automation for dark storytelling video pipeline.

## Development

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

To install dependencies:

```bash
uv sync
```

Run the pipeline:

```bash
uv run run_pipeline.py
```

You can also use the provided `Makefile`:

```bash
make sync
make run
```
