# Manual Testing Runbook

## Prereqs

- Docker and Docker Compose
- `uv`
- `pnpm`
- `ffmpeg` only if you want to inspect assets locally outside containers
- A populated `.env`
- At least one local background asset in `/content/visuals`
- At least one music track in `/content/audio/music`

## Setup

1. Install dependencies:
   ```bash
   uv sync
   pnpm install
   ```
2. Start the stack:
   ```bash
   make migrate
   make up
   make renderer
   ```
3. Verify services:
   ```bash
   curl http://localhost:8000/readyz
   open http://localhost:3000
   ```

## Seed a story

Use either the ingestor or a direct API call.

### Option A: direct API call

```bash
curl -X POST http://localhost:8000/stories \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "The figure outside my upstairs window",
    "body_md": "I was home alone when I heard scratching at the glass. When I looked up, something was already staring back at me."
  }'
```

### Option B: Reddit ingestion

```bash
make ingest
```

## Operator workflow test

1. Open `/inbox`.
2. Open a story and confirm the review page shows source text.
3. Click `Generate Script`.
   Expected:
   - Story status becomes `scripted`
   - Hook, narration draft, and outro appear
4. Click `Approve Story`.
   Expected:
   - Story status becomes `approved`
5. Open `/story/{id}/split`.
6. Edit the part text and click `Save Parts`.
   Expected:
   - Parts persist after refresh
7. Open `/story/{id}/media`.
8. Click `Apply Best Matches` and then `Save Bundle`.
   Expected:
   - Story status becomes `media_ready`
   - Bundle preview shows selected assets
9. Open `/story/{id}/queue`.
10. Queue short renders and leave weekly compilation enabled.
    Expected:
    - Browser navigates to `/story/{id}/jobs`
    - Jobs appear with `Queued` or `Claimed`

## Renderer test

1. Tail renderer logs:
   ```bash
   make renderer-logs
   ```
2. Wait for the worker to claim the queued jobs.
   Expected log events:
   - `poll`
   - `claim`
   - `heartbeat`
   - `done`
3. Confirm artifacts exist:
   ```bash
   find output -type f | sort
   ```
4. Inspect a short-form artifact with ffprobe:
   ```bash
   ffprobe -v error -show_streams -show_format output/*.mp4
   ```
   Expected:
   - One video stream
   - One audio stream
   - Duration roughly matches the part length
5. Confirm sidecar subtitles exist next to the rendered video when applicable.

## Weekly compilation test

1. After short artifacts are rendered, check the jobs page again.
2. Confirm the `render_compilation` job moves to `Rendered` or `Publish Ready`.
3. Verify the weekly artifact exists in `output/`.
4. Play the file locally and confirm the part order is correct.

## Publish queue test

1. Open `/publish`.
2. Confirm rendered releases appear in the queue.
3. Click `Mark Published` for one release.
   Expected:
   - Release disappears from the queue after refresh
   - Story status can move to `published`

## Failure-path checks

### Missing visuals

1. Empty `/content/visuals`.
2. Retry media indexing or queueing.
   Expected:
   - No bundle can be created
   - The UI or API returns a clear error

### Missing music

1. Empty `/content/audio/music`.
2. Queue a short render.
   Expected:
   - Render still succeeds if music is optional
   - Logs show the music fallback behavior

### Bad TTS config

1. Remove `ELEVENLABS_VOICE_ID`.
2. Restart the renderer and queue a job.
   Expected:
   - Renderer logs a configuration warning or render error
   - Job ends in `errored`

### Stale worker

1. Stop the renderer container while jobs are in progress.
2. Confirm jobs stop advancing and leases eventually expire.

## Local verification commands

```bash
uv run python -m pytest tests/api/test_render_jobs_api.py tests/api/test_stories_endpoints.py tests/api/test_render_endpoint.py tests/test_renderer_poller.py tests/renderer/test_disk_and_temp.py -q
pnpm --dir apps/web typecheck
pnpm --dir apps/web test -- --runInBand
```
