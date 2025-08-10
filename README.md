# dark-life

Monorepo for automating short-form dark storytelling videos.

## OS dependencies

- `ffmpeg`
- Node.js 20
- Python 3.10+
- Docker & Docker Compose

Install `ffmpeg` on Debian/Ubuntu with:

```bash
sudo apt install ffmpeg
```

## Local runbook

1. **Copy environment files**
   - `cp .env.sample .env`
   - `cp apps/api/.env.sample apps/api/.env`
   - `cp apps/web/.env.sample apps/web/.env`
   - Fill in API keys and secrets as described below.

2. **Start core services**

```bash
make up
```

This starts Postgres, Redis, the FastAPI backend on `8000` and the Next.js web app on `3000`.

3. **Run the renderer worker**

```bash
make renderer
```

4. **Use the web app** – open [`http://localhost:3000`](http://localhost:3000) and create a story, fetch/select images, split into parts, and enqueue the series.

5. **Check outputs** – rendered videos and manifests are written to `output/videos/` and `output/manifest/`.

6. **Upload to YouTube (optional)**

```bash
make uploader
```

On first run this performs the OAuth flow and stores the token.

7. **Verify with the smoke test**

```bash
make smoke
```

Use `make down` to stop the Docker services when finished.

## Environment variables

### Root `.env`

| Key | Description |
| --- | ----------- |
| `POSTGRES_USER` | Postgres user created for the development database |
| `POSTGRES_PASSWORD` | Password for the Postgres user |
| `POSTGRES_DB` | Name of the development database |
| `POSTGRES_PORT` | Local port exposed for Postgres |
| `DATABASE_URL` | Full connection URL for Postgres |
| `REDIS_URL` | Connection string for Redis |
| `PEXELS_API_KEY` | API key used for image search |
| `PIXABAY_API_KEY` | API key used for image search fallback |
| `OPENAI_API_KEY` | API key used by renderer services for narration |
| `ELEVENLABS_API_KEY` | API key for voice synthesis |
| `WHISPER_MODEL` | Whisper model name to use for transcription |
| `YOUTUBE_CLIENT_SECRETS_FILE` | Path to OAuth client secrets JSON for YouTube uploads |
| `YOUTUBE_TOKEN_FILE` | Path to stored OAuth token for YouTube |
| `NEXT_PUBLIC_API_BASE_URL` | Base URL the web app uses to reach the API |

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

## YouTube OAuth setup

1. Create an OAuth client ID (Desktop application) in the Google Cloud Console and download the `client_secrets.json` file.
2. Save it at the path pointed to by `YOUTUBE_CLIENT_SECRETS_FILE` in your `.env`.
3. Run `make uploader` once. If `YOUTUBE_TOKEN_FILE` does not exist, a browser window opens to complete the OAuth flow and the token is saved to that path.
4. Subsequent `make uploader` runs will upload the next rendered part using the stored token.

To automate uploads daily at 9 AM, add a crontab entry like:

```bash
0 9 * * * cd /path/to/dark-life && python cron_upload.py
```

## Development

This project uses [uv](https://github.com/astral-sh/uv) for Python dependency management and Next.js for the web frontend. Standard `make` targets are available for running tests and individual services:

```bash
make init    # set up the Python virtual environment
make test    # run the test suite
make smoke   # run the end-to-end smoke test
```

## Smoke test

After the stack and renderer worker are running, execute:

```bash
make smoke
```

This script creates a sample story, fetches images, splits the story,
enqueues render jobs, waits for them to finish, verifies the output files, and
can optionally perform an uploader dry-run with `--uploader`.

