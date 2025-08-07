# dark-life

Automation for dark storytelling video pipeline.

## Development

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

To set up the project and install dependencies:

```bash
make init
```

This will create a local virtual environment (if needed) and install dependencies via uv.

You can also call uv directly:

```bash
uv sync
```

Run the pipeline:

```bash
uv run run_pipeline.py
```

You can also use the provided `Makefile`:

```bash
make init   # create venv and install dependencies
make run    # run the pipeline
```

## Configuration

Copy `sample.env` to `.env` and fill in the required API keys. The project uses `python-dotenv` to load these values automatically.
