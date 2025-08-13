# AGENTS.md — Renderer Service (API Polling → Render → Output)

Weapons-grade production-ready renderer spec.  
Polling is to the API, not the DB directly.  
Plain text for copy-paste.

================================================================================
## Goals
- Deterministic renders with background music from `/content/audio/music`.
- Clear, structured logs at each stage: API poll → claim → preflight → render → write → API status update.
- Fail fast on misconfig (paths, missing frames/audio) with actionable errors.
- Zero-secret leakage; safe to run under docker compose locally and in production.

================================================================================
## Agents

### 1) Renderer Worker (API Poller)
**Objective:** Poll the API for pending jobs, claim them atomically, and dispatch to the slideshow renderer.

**Responsibilities**
- Poll API endpoint at `POLL_INTERVAL_MS` with jitter; log `queue_depth` (from API response).
- API endpoint: `GET /api/render-jobs?status=queued&limit=MAX_CLAIM` returns claim tokens.
- Claim job via `POST /api/render-jobs/{id}/claim` (returns lease expiry); log `{job_id, story_id, part_id, lease_sec}`.
- Enforce concurrency via semaphore (`MAX_CONCURRENT`).
- Heartbeat logs while a job is running; extend lease via `POST /api/render-jobs/{id}/heartbeat`.
- Retry policy with exponential backoff on HTTP 5xx or network errors; no retry on 4xx except 409 (conflict).

**Inputs**
- API base URL + auth token.
- Config/env: `POLL_INTERVAL_MS`, `MAX_CONCURRENT`, `LEASE_SECONDS`.
- Paths: `/content`, `/output`, `/tmp/renderer`.

**Outputs**
- Job status transitions via API calls: `queued → claimed → rendering → rendered|errored`.
- Per-job structured logs (JSON).

---

### 2) Slideshow Renderer
**Objective:** Create a video from prepared frames and background music.

**Responsibilities**
- Preflight: validate frames dir non-empty; choose music track deterministically; ffprobe both.
- Build ffmpeg command with explicit stream mapping and `-shortest`.
- Render to a temp file, then atomic rename to `/output/<storyId>_<partIndex>.mp4`.
- Return artifact metadata (size, duration, selected audio).

**Inputs**
- Frames directory for the job (e.g., `/tmp/renderer/<job_id>/frames`).
- Music directory: `/content/audio/music` (absolute).
- Render settings: fps, codecs, bitrate.

**Outputs**
- MP4 under `/output/…`.
- Metadata for API update.
- Detailed logs + ffmpeg stderr snippet on failure.

---

### 3) Shared Config & Logging
**Objective:** Provide absolute paths and structured logging helpers so all agents behave consistently.

**Responsibilities**
- Constants:
  - `CONTENT_DIR=/content`
  - `MUSIC_DIR=/content/audio/music`
  - `OUTPUT_DIR=/output`
  - `TMP_DIR=/tmp/renderer`
- Logging helpers: `log_info(event, **fields)`, `log_error(event, **fields)`, JSON formatter.
- CLI flags: `--log-level`, `--json-logs`, `--debug`.

================================================================================
## Interfaces & Contracts

### API endpoints
- `GET /api/render-jobs?status=queued&limit=N` → list of `{id, story_id, part_id, claim_url, lease_seconds}`.
- `POST /api/render-jobs/{id}/claim` → `{lease_expires_at}`.
- `POST /api/render-jobs/{id}/heartbeat` → 200 OK if extended.
- `POST /api/render-jobs/{id}/status` with body:
  - `status`: `rendering|rendered|errored`
  - `artifact_path?`, `bytes?`, `duration_ms?`
  - `error_class?`, `error_message?`, `stderr_snippet?`

### Renderer inputs
- `frames_dir`: must exist and contain at least one `*.png`.
- `music_dir`: must contain at least one `.mp3` (default pick: first sorted).
- `fps`: default 30.
- `audio_bitrate`: default 192k.

### Renderer outputs
- `artifact_path`: `/output/<storyId>_<partIndex>_<ts>.mp4` (atomic rename).
- `bytes`, `duration_ms`, `audio_track`: logged + sent to API.

================================================================================
## Logging Specification

- All logs are single-line JSON in INFO level unless noted.
- Required fields: `service="renderer"`, `event`, `job_id`, `story_id`, `part_id` (when known).
- Timestamps from logger, not manual.

**Startup**
`{"service":"renderer","event":"start","poll_interval_ms":5000,"max_concurrent":2,"lease_seconds":120,"api_base":"https://api.example.com","content_dir":"/content","music_dir":"/content/audio/music","output_dir":"/output"}`

**Poll tick**
`{"service":"renderer","event":"poll","queue_depth":3}`

**Claim**
`{"service":"renderer","event":"claim","job_id":"J123","story_id":"S45","part_id":"P2","lease_expires_at":"...","attempt":1}`

**Preflight**
`{"service":"renderer","event":"preflight","job_id":"J123","frames_dir":"/tmp/renderer/J123/frames","frame_count":450,"music_dir":"/content/audio/music","chosen_track":"background.mp3"}`

**ffmpeg command (DEBUG only)**
`{"service":"renderer","event":"ffmpeg_cmd","argv":["ffmpeg","-y","-framerate","30","-pattern_type","glob","-i","/tmp/renderer/J123/frames/*.png","-i","/content/audio/music/background.mp3","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-shortest","-map","0:v:0","-map","1:a:0","/output/S45_P2.mp4"]}`

**Heartbeat (every 5–10s during render)**
`{"service":"renderer","event":"rendering","job_id":"J123","elapsed_sec":42}`

**Success**
`{"service":"renderer","event":"done","job_id":"J123","path":"/output/S45_P2.mp4","bytes":8345234,"duration_ms":59874}`

**Error**
`{"service":"renderer","event":"error","job_id":"J123","exit_code":1,"error_class":"FFmpegError","stderr_snippet":"...muxer error...","ffreport":"/tmp/ffreport-J123.log"}`

================================================================================
## Operational Settings (env/CLI)

- `API_BASE_URL` (required)
- `API_AUTH_TOKEN` (required)
- `POLL_INTERVAL_MS` (default 5000)
- `MAX_CONCURRENT` (default 1 or 2)
- `LEASE_SECONDS` (default 120)
- `MUSIC_DIR=/content/audio/music`
- `CONTENT_DIR=/content`
- `OUTPUT_DIR=/output`
- `TMP_DIR=/tmp/renderer`
- Flags: `--log-level info|debug`, `--json-logs`, `--debug`

Docker Compose (renderer service) should ensure:
- `PYTHONUNBUFFERED=1`
- Command calls Python unbuffered and passes absolute paths:
  `python -u video_renderer/create_slideshow.py --music-dir /content/audio/music --stories-path /content/stories --output /output`

================================================================================
## Failure Policy

- **Preflight failure** (no frames/audio): mark `errored` via API with reason; do not call ffmpeg.
- **ffmpeg failure**: capture `stderr` + exit code, mark `errored` via API; retry up to `MAX_RETRIES` with backoff for transient codes.
- **Lease expired**: if a render exceeds lease, renew lease via heartbeat or abort gracefully and mark `errored` via API.
- **Timeout**: kill ffmpeg after `JOB_TIMEOUT_SEC`; mark `errored` with `timeout=true`.

================================================================================
## Runbooks

### A) Fresh run
1. `docker compose -f infra/docker-compose.yml up --build renderer`
2. Follow logs: `docker compose -f infra/docker-compose.yml logs -f --tail=0 renderer`
3. Expect `start` → `poll` → (maybe `claim`) → `preflight` → `rendering` → `done`.

### B) No output showing
- Ensure unbuffered: `PYTHONUNBUFFERED=1` and `python -u`.
- Run directly:

docker compose -f infra/docker-compose.yml run –rm –no-deps renderer 
python -u video_renderer/create_slideshow.py 
–stories-path /content/stories 
–output /output 
–music-dir /content/audio/music

- If still silent: add `--debug` and inspect FFREPORT path in logs.

### C) Audio missing
- Verify path: `ls -l /content/audio/music`
- Preflight logs must show `chosen_track`.
- If empty dir, mount host `./content` into `/content` in compose.
- If multiple tracks: default select first sorted; set `--music-select=named:background.mp3` if supported.

### D) Disk/space issues
- Preflight log `df -h` when `--debug` is on; refuse when `< 2GB` free.
- Temp cleanup: on error/success remove `/tmp/renderer/<job_id>`.

================================================================================
## Acceptance Criteria
- Poll loop hits API and logs queue depth even when idle.
- Absolute defaults used; `--music-dir /content/audio/music` not required.
- Structured logs at every stage with `job_id/story_id/part_id`.
- On failure, `stderr_snippet` is present and API updated to `errored`.
- Output files atomically written to `/output` with non-zero size and audio stream present.
- Heartbeats extend leases; no job lost to timeout without attempt to renew.