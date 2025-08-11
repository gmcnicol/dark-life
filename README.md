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

3. **Migrate & start**
   ```bash
   docker compose -f infra/docker-compose.yml build
   make migrate   # apply migrations before starting the API
   make up
   ```

4. **Open services**
   - Web: <http://localhost:3000>
   - API health: <http://localhost:8000/readyz>

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

## Running Migrations

Run database migrations from the repository root once your `.env` is configured, before starting the API:

```bash
docker compose -f infra/docker-compose.yml run --rm api sh -lc 'cd apps/api && alembic upgrade head'
```

### Admin endpoints

Admin APIs require `Authorization: Bearer $ADMIN_API_TOKEN`.

## Reddit Ingestion

The Reddit ingestor uses the official API. When paging `subreddit.new()` there
is a practical cap of roughly 1000 items; historical range queries are not
guaranteed. Backfill performs bounded paging and optionally attempts
cloudsearch time windows. These windows are best-effort and may return zero
results without failing the job. Fetching deep history beyond the official API
limits requires Pushshift or moderator-only keys.

Sanity check:

```bash
docker compose -f infra/docker-compose.yml --profile ops run --rm reddit_ingestor sh -lc '
python - <<PY
import os,praw
r=praw.Reddit(client_id=os.environ["REDDIT_CLIENT_ID"], client_secret=os.environ["REDDIT_CLIENT_SECRET"], user_agent=os.environ.get("REDDIT_USER_AGENT","darklife/1.0"))
items=list(r.subreddit("nosleep").new(limit=5))
print("fetched",len(items),"newest nosleep")
for s in items: print(s.id, int(s.created_utc), s.title[:80])
PY
'
```

## Environment variables

See [`.env.sample`](.env.sample) for the full list of configuration options.

## Renderer & Uploader

The renderer polls the database for jobs and writes videos to `./output`. Schedule the uploader with cron or CI to publish rendered parts regularly.
