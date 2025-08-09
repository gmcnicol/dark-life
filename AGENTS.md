# AGENTS.md — Dark Life POC (Happy-Path to Daily Shorts)

Goal
-----
Implement the end-to-end workflow TODAY: create/edit a story in the web app → auto-fetch & select images → split into 60-second parts → enqueue a render SERIES (one job per part) → renderer produces numbered MP4s with burned subtitles → uploader posts ONE part per day (start with YouTube Shorts).

Constraints / Principles
------------------------
- Keep it simple and deterministic. No auth/roles or heavy infra in this POC.
- FFmpeg + Whisper only (no MoviePy). ElevenLabs optional; fallback OK.
- Idempotent endpoints and workers. Safe to re-run.
- Everything runnable locally on Linux from the README/Makefile.

Prereqs (ensure .env.sample covers these)
-----------------------------------------
DATABASE_URL=postgresql://user:pass@postgres:5432/darklife
REDIS_URL=redis://redis:6379/0
PEXELS_API_KEY=... (or PIXABAY_API_KEY=...)
WHISPER_MODEL=base (or small)
YOUTUBE_CLIENT_SECRETS=./secrets/client_secret.json
YOUTUBE_TOKEN=./secrets/token.json
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

Repository Assumptions
----------------------
apps/api              FastAPI + SQLAlchemy/SQLModel + Alembic
apps/web              Next.js (TypeScript, App Router, Tailwind, shadcn/ui)
services/renderer     Worker: Whisper + FFmpeg slideshow builder
services/uploader     Uploader scripts + scheduler
infra/                docker-compose, migrations, dev docs
output/               videos/ (mp4) and manifest/ (json)
content/              visuals/, audio/ (if any)

Execution Order (Phased Workplan)
---------------------------------
PHASE 1 — Bring-up & Ops Glue
PHASE 2 — Stories CRUD + Image Picker (Web ↔ API)
PHASE 3 — Split Story into ~60s Parts
PHASE 4 — Enqueue SERIES and Render Per-Part
PHASE 5 — Daily Uploader (YouTube Shorts POC)
PHASE 6 — Smoke Test & README polish

Acceptance at the end: “make up”; create/edit story in the web; fetch/select images; split; enqueue series; renderer outputs {slug}_p01.mp4… with subs; uploader posts next part; smoke test passes.

-------------------------------------------------------------------------------
PHASE 1 — Bring-up & Ops Glue
-------------------------------------------------------------------------------
Codex: 
1) Add renderer/uploader containers or Make targets.
   - infra/docker-compose.yml: services for postgres, redis, api (:8000), web (:3000).
   - Either add renderer/uploader as additional services OR provide:
       make up           -> compose up db, redis, api, web
       make renderer     -> run services/renderer/poller.py with env + volumes
       make uploader     -> run services/uploader/cron_upload.py (dry-run supported)
2) Update README:
   - Linux commands (apt install ffmpeg; python, node versions).
   - First run: docker compose up --build, then make renderer.
   - Where outputs land: output/videos/*.mp4, output/manifest/*.json
   - YouTube OAuth token bootstrap (one-time).

Acceptance:
- Fresh clone + .env populated → “make up” starts db/redis/api/web; “make renderer” logs “polling…”.

-------------------------------------------------------------------------------
PHASE 2 — Stories CRUD + Image Picker (Web ↔ API)
-------------------------------------------------------------------------------
DB: tables stories(id, slug, title, subreddit, source_url, status enum[draft,approved,ready,rendered,uploaded], body_md, created_at, updated_at), assets(id, story_id, type=image, provider, remote_url, local_path nullable, selected bool, rank int, meta jsonb, created_at).

API endpoints:
- POST   /api/stories                      {title, subreddit?, source_url?, body_md, status?}
- GET    /api/stories?status=&q=&page=&limit=
- GET    /api/stories/{id}
- PATCH  /api/stories/{id}                 {title?, body_md?, status?}
- DELETE /api/stories/{id}
- POST   /api/stories/{id}/fetch-images    -> queries Pexels (fallback Pixabay), stores Asset rows (selected=false, rank=null, meta raw provider payload). Do NOT download originals yet.
- GET    /api/stories/{id}/images
- PATCH  /api/stories/{id}/images/{assetId}  {selected?:bool, rank?:int}
Keyword extraction: simple regex list (cabin, forest, fog, attic, window, shadow, alley, night, mist, abandoned, etc.) from title + body.

Web:
- /stories: list with search + status filter.
- /stories/[id]: editor (title, body_md). Autosave w/ debounce; toasts on save.
- “Images” tab: button “Auto-fetch images” → grid of candidates; select/unselect; drag-sort; PATCH ranks & selected.

Acceptance:
- Create dummy story in UI; fetch images; select at least 3; reorder → state persists.

-------------------------------------------------------------------------------
PHASE 3 — Split Story into ~60s Parts
-------------------------------------------------------------------------------
DB: story_parts(id, story_id, index (1-based), body_md, est_seconds, created_at, updated_at).

API:
- POST /api/stories/{id}/split?target_seconds=60
  Logic:
  - Approximate WPM 160; compute tokens/words per part = target_seconds * (WPM/60).
  - Split on sentence boundaries near that budget (keep coherence).
  - Persist parts with index ascending and est_seconds.
  - Return parts.

Web:
- In /stories/[id], “Parts” tab appears after split; list parts with index and preview text.

Acceptance:
- A ~600–900 word story splits into 3–5 reasonable 60s parts; parts visible in UI.

-------------------------------------------------------------------------------
PHASE 4 — Enqueue SERIES and Render Per-Part
-------------------------------------------------------------------------------
DB: jobs(id, story_id, kind enum[render_part, upload], status enum[queued,running,success,failed], payload jsonb, result jsonb, created_at, updated_at). Ensure indexes on (status, kind), (story_id).

API:
- POST /api/stories/{id}/enqueue-series
  - Preconditions: story has ≥1 selected image; if no parts, call split (60s).
  - For each part: create Job(kind=render_part,status=queued,payload={story_id, part_index, selected_asset_ids (ordered), preset:"slideshow_9x16_fade", subtitle:true})
  - Set story.status="ready"
  - Return job IDs

Renderer worker (services/renderer/poller.py):
- Poll jobs where kind=render_part AND status=queued.
- Transition to running; record started_at.
- Materialize inputs:
  - Download/copy selected images to a temp working dir (or local_path if already cached on selection).
  - Narration audio for this PART:
      If TTS configured, synthesize; else fallback: generate from text via pyttsx3 or use placeholder mp3.
  - Subtitles: run Whisper/faster-whisper on the PART audio → {story_id}_p{xx}.srt
- FFmpeg slideshow:
  - 1080x1920; images crossfade 1s; per-image ~5s; dark overlay (drawbox), light zoom (zoompan), low saturation.
  - Burn subtitles: -vf subtitles=... (or ASS if styled).
  - Mix narration + optional background loop (if present).
  - Output: output/videos/{slug}_p{index:02}.mp4
- Write/update manifest: output/manifest/{story_id}.json { parts: [{index, output_path, duration_s}], created_at }
- Mark job success with result { output_path, part_index, duration_s }. On error: status=failed + error.

Acceptance:
- Enqueue series → renderer produces numbered MP4s with subs; jobs move to success.

-------------------------------------------------------------------------------
PHASE 5 — Daily Uploader (YouTube POC)
-------------------------------------------------------------------------------
DB: uploads(id, story_id, part_index, platform text ("youtube"), platform_video_id text, uploaded_at timestamptz). Add unique on (story_id, part_index, platform).

Uploader (services/uploader/upload_youtube.py):
- Find next unpublished rendered part:
  - Prefer smallest story_id with parts rendered but not uploaded to YouTube; then smallest part_index not uploaded.
  - Upload via YouTube Data API with Shorts constraints (vertical; ≤ 60s).
  - Title: "{story_title} — Part {index}"; description from story; tags optional.
  - On success: insert uploads row & return video ID/URL.

Scheduler (services/uploader/cron_upload.py):
- CLI flags: --dry-run, --limit 1
- Default behavior: upload exactly one part per run.

README:
- Add crontab example (Linux): e.g., daily 10:00 local time
  0 10 * * * cd /path/to/repo && /usr/bin/env bash -lc "make uploader"

Acceptance:
- With rendered parts, a manual run uploads p01, logs URL, records DB row. Subsequent runs upload next part.

-------------------------------------------------------------------------------
PHASE 6 — Smoke Test & README polish
-------------------------------------------------------------------------------
scripts/smoke_e2e.py (idempotent happy-path):
- Create story (POST /api/stories).
- Fetch images, select first 3, rank.
- Split (60s).
- Enqueue series.
- Poll /api/jobs/{id} until success for all parts (or timeout).
- Verify output files exist.
- Optionally dry-run uploader to select next part.

Make target:
- make smoke

README:
- “Local POC Runbook” with exact steps:
  1) cp .env.sample .env; fill keys
  2) docker compose up --build
  3) make renderer
  4) open http://localhost:3000, create story, fetch/select images, split, queue series
  5) watch output/videos/
  6) run uploader (manual or cron)
  7) make smoke to validate

Acceptance:
- “make up”; web workflow works; renderer outputs; uploader posts; smoke passes.

Endpoint Contracts (for avoidance of doubt)
-------------------------------------------
POST /api/stories
  In:  {title, subreddit?, source_url?, body_md, status?}
  Out: {id, slug, ...}

GET /api/stories?status=&q=&page=&limit=
  Out: [{id, title, status, updated_at, ...}]

GET /api/stories/{id}
  Out: {id, title, body_md, status, ...}

PATCH /api/stories/{id}
  In:  {title?, body_md?, status?}
  Out: {id, ...}

POST /api/stories/{id}/fetch-images
  Out: {count, provider:"pexels", created:[assetIds...]}

GET /api/stories/{id}/images
  Out: [{id, provider, remote_url, selected, rank, meta}...]

PATCH /api/stories/{id}/images/{assetId}
  In:  {selected?:bool, rank?:int}
  Out: {id, selected, rank}

POST /api/stories/{id}/split?target_seconds=60
  Out: [{id, index, est_seconds, body_md}...]

POST /api/stories/{id}/enqueue-series
  Out: {jobs:[{id, part_index}...]}

GET /api/jobs?story_id=&kind=&status=
GET /api/jobs/{id}
  Out: {id, kind, status, payload, result}

DB Migrations Summary
---------------------
CREATE TABLE stories (...);
CREATE TABLE assets (..., FOREIGN KEY story_id -> stories.id);
CREATE TABLE story_parts (..., FOREIGN KEY story_id -> stories.id);
CREATE TABLE jobs (..., INDEX(kind,status), FOREIGN KEY story_id -> stories.id);
CREATE TABLE uploads (..., UNIQUE(story_id, part_index, platform));

Makefile Targets (suggested)
----------------------------
make up            # compose up db, redis, api, web
make down          # stop
make renderer      # run renderer worker locally
make uploader      # run uploader once (respects --dry-run by env)
make smoke         # run scripts/smoke_e2e.py

Quality Bar (Today)
-------------------
- Linted & typed where possible.
- Clear logs (what job, which part, which file, ffmpeg cmd).
- Deterministic defaults (60s target; 3–6 images min).
- Errors don’t crash the stack; jobs marked failed with reasons.

Exit Criteria (Today)
---------------------
- From the web UI: create/edit story → fetch/select images → split → enqueue series.
- Renderer outputs numbered vertical MP4s with burned subtitles.
- Uploader posts one part on demand; records platform id.
- Smoke test passes locally.

Notes
-----
- If TTS is not ready, use placeholder audio + Whisper on the text via TTS fallback or skip subs for POC (but keep the code path).
- Image licensing: store provider payload in assets.meta; attribution handled later.
- If Redis is not used today, polling DB for jobs is fine for the POC.

# END
