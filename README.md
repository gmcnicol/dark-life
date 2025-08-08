# dark-life

Monorepo for automating short-form dark storytelling videos.

## Running with Docker Compose

1. **Copy environment files**
   - `cp .env.sample .env`
   - `cp apps/api/.env.sample apps/api/.env`
   - `cp apps/web/.env.sample apps/web/.env`
   - Fill in API keys and secrets as described below.

2. **Start the stack**

```bash
cd infra
docker compose up --build
```

This brings up Postgres, Redis, the FastAPI backend on port `8000` and the Next.js web app on port `3000`.

Visit [`http://localhost:3000`](http://localhost:3000) for the web UI and [`http://localhost:8000/health`](http://localhost:8000/health) for a basic API health check.

## Environment variables

### Root `.env`

| Key | Description |
| --- | ----------- |
| `POSTGRES_USER` | Postgres user created for the development database |
| `POSTGRES_PASSWORD` | Password for the Postgres user |
| `POSTGRES_DB` | Name of the development database |
| `POSTGRES_PORT` | Local port exposed for Postgres |
| `REDIS_URL` | Connection string for Redis |
| `PEXELS_API_KEY` | API key used for image search |
| `PIXABAY_API_KEY` | API key used for image search fallback |
| `OPENAI_API_KEY` | API key used by renderer services for narration |
| `ELEVENLABS_API_KEY` | API key for voice synthesis |

### `apps/api/.env`

| Key | Description |
| --- | ----------- |
| `DATABASE_URL` | SQLAlchemy connection URL for Postgres |
| `REDIS_URL` | Connection string for Redis |
| `PEXELS_API_KEY` | API key used for image search |
| `PIXABAY_API_KEY` | API key used for image search fallback |
| `OPENAI_API_KEY` | API key used for AI features |
| `ELEVENLABS_API_KEY` | API key for voice synthesis |

### `apps/web/.env`

| Key | Description |
| --- | ----------- |
| `NEXT_PUBLIC_API_BASE_URL` | Base URL the web app uses to reach the API |

## Renderer and Uploader Integration

Existing renderer and uploader services live in the `video_renderer/` and `video_uploader/` directories. The FastAPI backend creates render jobs that these services can consume. Ensure they share access to the same `.env` values and directories (`render_queue/` and `output/`) when running them alongside the stack.

## Development

This project uses [uv](https://github.com/astral-sh/uv) for Python dependency management and Next.js for the web frontend. Standard `make` targets are available for running tests and individual services:

```bash
make init    # set up the Python virtual environment
make test    # run the test suite
```

