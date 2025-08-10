# dark-life

Monorepo for automating short-form dark storytelling videos.

## Local POC Runbook

1. **Prereqs**
   - Docker & Compose
   - Node 20
   - Python 3.11
   - `ffmpeg` (only if running tools outside containers)

2. **Setup**
   ```bash
   cp .env.sample .env
   ```
   Fill any optional API keys and secrets. `ADMIN_API_TOKEN` defaults to `local-admin`.

3. **Build & start**
   ```bash
   docker compose -f infra/docker-compose.yml build
   make up
   make migrate
   ```

4. **Open services**
   - Web: <http://localhost:3000>
   - API health: <http://localhost:8000/health>

5. **Renderer & uploader**
   ```bash
   make renderer      # start background renderer
   make uploader      # run upload once
   ```

6. **Troubleshooting**
   - `pnpm-lock.yaml not found` → web uses npm Dockerfile
   - `psycopg not found` → ensure `psycopg[binary]` installed and rebuild API
   - Database connection errors → `DATABASE_URL` must use host `postgres`
   - `8000` in use → change host mapping to `8001:8000`

### Admin endpoints

Admin APIs require `Authorization: Bearer $ADMIN_API_TOKEN`.

## Environment variables

See [`.env.sample`](.env.sample) for the full list of configuration options.

## Renderer & Uploader

The renderer polls the database for jobs and writes videos to `./output`. Schedule the uploader with cron or CI to publish rendered parts regularly.
