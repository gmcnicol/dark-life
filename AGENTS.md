# AGENTS.md — Dark Life (Phase: Database & Ingestion Enablement)

This phase ensures:
1) The API applies Alembic migrations automatically on startup (zero schema drift).
2) The Reddit ingestion service reliably and idempotently inserts stories into the database.

---

## Goals

- **Zero-drift schema:** API only becomes *ready* after `alembic upgrade head` succeeds.
- **Idempotent ingestion:** Dedupe on `(source, external_id)`; upsert on conflict.
- **Observable ops:** Structured logs, health/readiness gating, simple runbooks and alerts.

---

## Components (Agents)

### 1) API Service (Migration Executor)
**Purpose:** Start with the latest DB schema and expose admin endpoints used by ingestors.

**Responsibilities**
- Read DB URL from environment and run `alembic upgrade head` *before* starting the app server.
- Exit non-zero on migration failure (fail fast).
- Expose protected admin endpoints used for ingestion (e.g. `POST /admin/stories`).
- Report **readiness** only after migrations succeed and the HTTP server is accepting requests.

**Key Environment**
- `DATABASE_URL` — e.g. `postgresql+psycopg://user:pass@postgres:5432/darklife`
- `ADMIN_API_TOKEN` — bearer token for admin/ingestion endpoints
- `PORT` (optional) — default `8000`

**Entrypoint (reference)**
    #!/usr/bin/env sh
    set -euo pipefail
    echo "[api] running alembic upgrade head..."
    alembic upgrade head
    echo "[api] starting server..."
    exec uvicorn apps.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"

**Health / Readiness**
- `/healthz`: returns 200 when the process is up.
- `/readyz`: returns 200 **only after** migrations have succeeded and the server is ready to serve traffic.
- Compose should gate API startup on Postgres health, then consumers (e.g., ingestor) can depend on API readiness.

**Compose hints**
    services:
      postgres:
        healthcheck:
          test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
          interval: 5s
          timeout: 5s
          retries: 20

      api:
        depends_on:
          postgres:
            condition: service_healthy

**Failure modes**
- Migration error → container exits non-zero → no ready signal → upstream services will not start or will retry.
- Missing `DATABASE_URL` → immediate failure (log and exit).
- Admin endpoint disabled/missing token → ingestor will 401 and back off (see ingestor retries).

---

### 2) Reddit Ingestor
**Purpose:** Fetch Reddit posts and persist them via the API (preferred) or directly to DB (fallback), idempotently.

**Responsibilities**
- Fetch newest posts for configured subreddits with bounded pagination.
- Transform each post into `StoryIn` and send to API.
- Ensure idempotency via `(source, external_id)`; on conflict, update mutable fields (title, text, url, tags).
- Support **one-shot** (backfill) and **daemon** (continuous) modes.
- Emit structured JSON logs and simple counters (ingested, upserts, duplicates, errors).

**Key Environment**
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`
- `API_BASE_URL` (e.g. `http://api:8000`)
- `ADMIN_API_TOKEN`
- `MODE` — `once` | `daemon`
- `SUBREDDITS` — comma-separated list (e.g., `nosleep,letsnotmeet`)
- `SINCE_EPOCH` (optional for backfill start)
- `POLL_INTERVAL_SECONDS` (daemon mode; default 300)

**Data Contract**
- `StoryIn`:
  - `external_id: str` (Reddit link/id)
  - `source: str` (constant `"reddit"`)
  - `title: str`
  - `author: str | null`
  - `created_utc: int`
  - `text: str | null`
  - `url: str | null`
  - `nsfw: bool | null`
  - `flair: str | null`
  - `tags: list[str] | null`

**API Contract (preferred path)**
- `POST /admin/stories` (Bearer `ADMIN_API_TOKEN`)
  - Body: `StoryIn`
  - 201 on insert; 200 on upsert/update; 409/422 with error body captured to logs/dead-letter.

**Idempotency**
- DB uniqueness constraint on `(source, external_id)`.
- On conflict: update text/title/url/tags/flair/nsfw; never change `created_utc`.

**Rate limits & retry**
- Respect Reddit API limits and backoff headers.
- Retries: 3 attempts with exponential backoff on 429/5xx.
- Permanent 4xx (except 409/422) → skip and log error.

**Modes**
- `MODE=once`: run bounded backfill; exit 0 when done.
- `MODE=daemon`: loop forever:
  - poll window (e.g., past N minutes) with jitter,
  - update checkpoint per subreddit (`last_seen_created_utc`),
  - sleep `POLL_INTERVAL_SECONDS`.

**Compose hints**
    services:
      reddit_ingestor:
        profiles: ["ops"]
        depends_on:
          api:
            condition: service_started
        environment:
          MODE: "daemon"
          SUBREDDITS: "nosleep,letsnotmeet"
          POLL_INTERVAL_SECONDS: "300"

**Exit codes**
- 0: success / normal exit (e.g., `MODE=once` completed).
- 10: input/config error (missing env, invalid subreddit list).
- 20: upstream/API unavailable after max retries.
- 30: validation error persisted beyond retries (record skipped).

---

## Runbooks

### First-time setup
1. Ensure Postgres is reachable and empty or at expected baseline.
2. Set `DATABASE_URL` in API env and `ADMIN_API_TOKEN`.
3. Boot API container; confirm:
   - logs show `alembic upgrade head` succeeded,
   - `/readyz` returns 200.
4. Hit admin list endpoint (if available) to verify auth path.

### Local development
- Create a migration:
    docker compose -f infra/docker-compose.yml run --rm api sh -lc 'cd apps/api && alembic revision --autogenerate -m "your message"'
- Apply migrations (happens automatically on start); to force manually:
    docker compose -f infra/docker-compose.yml run --rm api sh -lc 'cd apps/api && alembic upgrade head'

### Backfill (one-shot)
- Run ingestor with a start point:
    MODE=once SUBREDDITS="nosleep" SINCE_EPOCH=1700000000 docker compose --profile ops up reddit_ingestor --build
- Verify counts in DB/API; re-run with adjusted `SINCE_EPOCH` as needed.

### Continuous ingest
- Run with:
    MODE=daemon SUBREDDITS="nosleep,letsnotmeet" POLL_INTERVAL_SECONDS=300 docker compose --profile ops up reddit_ingestor -d
- Monitor logs for upserts/duplicates; inspect checkpoints.

### After schema change
1. Create migration; merge conflicts if multiple heads arise.
2. Rebuild and restart API. Readiness will gate until migrations succeed.
3. Re-run ingestor (`once` for backfill of new fields or `daemon` to resume).

### Disaster recovery
- If API fails to migrate:
  - Inspect logs for SQL errors,
  - Roll forward with a fix migration, or roll back to prior revision,
  - Rebuild/restart until `/readyz` is 200.
- If ingestor hot-loops on bad data:
  - Confirm 4xx vs 5xx,
  - Quarantine the record (dead-letter),
  - Patch transformation or server-side validation; redeploy.

---

## Testing

**Unit**
- DTO validation for `StoryIn`.
- Upsert builder (ensures correct ON CONFLICT behavior or API upsert semantics).
- Reddit client pagination and backoff logic.

**Integration**
- Spin up Postgres + API.
- Run `MODE=once` against a fixed subreddit sample (or mocked Reddit API).
- Assert: row counts, dedupe behavior, and that re-runs do not increase totals.

---

## Observability

**Logs (JSON)**
- API: `event="alembic_upgrade" status="start|ok|error" from_rev=... to_rev=...`
- Ingestor: `event="ingest" subreddit=... inserted=... upserted=... duplicates=... errors=...`
- Errors include `err_type`, `http_status`, and `external_id`.

**Counters (suggested)**
- `ingestor_posts_inserted_total`
- `ingestor_posts_upserted_total`
- `ingestor_errors_total`
- `api_migration_runs_total{status="ok|error"}`

---

## Security

- Admin endpoints require `Authorization: Bearer ${ADMIN_API_TOKEN}`.
- Tokens are not logged; redact secrets in logs.
- Principle of least privilege on DB user used by API; ingestor should not have direct DB access in prod (API only).

---

## Acceptance Criteria (for this phase)

- API container exits non-zero if migrations fail; `/readyz` returns 200 only post-migration.
- Fresh environment boot applies latest migrations with no manual step.
- Ingestor can run `once` and `daemon` against at least one subreddit and:
  - inserts new stories,
  - upserts changed stories,
  - skips duplicates without growth,
  - survives transient 5xx/429 with backoff.
- Logs clearly show counts and errors for both agents.

