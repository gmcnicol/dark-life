# AGENTS.md — Renderer & Pipeline (API Polling → TTS (ElevenLabs) → Whisper Subs → Render → Output)

Date: 2025-08-14
Owner: Renderer/Platform
Status: Authoritative spec for the render pipeline. Copy into repo root.

==============================================================================
High-level Goal
- Weapons‑grade, production‑ready pipeline from ingested story parts to finished videos.
- Poll **API** (not DB) for jobs, synthesize voice via **ElevenLabs TTS**, generate subtitles via **Whisper (ASR)**, mix optional background music, render with ffmpeg, update job status in API.
- Strong observability and deterministic behavior. Zero leakage of admin secrets to browsers.

==============================================================================
System Overview
1) **Ingestion (Reddit → API):** Idempotent upsert of stories; maintains checkpoints.
2) **Splitting (API/Web):** Story split into parts with validated durations and sentence alignment.
3) **Renderer Worker (this doc):** Polls API for `queued` jobs; claims/leases; renders per part:
   - Generate **Voice Over** using ElevenLabs (TTS) from part text → `vo.wav`
   - Generate **Subtitles** using Whisper from `vo.wav` → `part.srt` (or `.vtt`)
   - Deterministically select background music from `/content/audio/music` (optional)
   - ffmpeg: frames (if applicable) + VO + music (ducking) → MP4 in `/output`
   - POST status to API (`rendering` → `rendered` | `errored`) with metadata
4) **Uploads/Publish:** Out of scope here.

==============================================================================
Environment & Configuration (authoritative, consistent names)
# Global (renderer/web/api)
- CONTENT_DIR=/content
- MUSIC_DIR=/content/audio/music
- OUTPUT_DIR=/output
- TMP_DIR=/tmp/renderer
- LOG_LEVEL=info            # debug|info|warn|error
- JSON_LOGS=true            # emit single-line JSON logs
- DEBUG=false               # turns on ffmpeg verbose + FFREPORT
- JOB_TIMEOUT_SEC=900       # kill long-running ffmpeg/tts runs
- MAX_CONCURRENT=2
- POLL_INTERVAL_MS=5000
- LEASE_SECONDS=180

# API access (used by renderer worker; NEVER exposed to browser)
- API_BASE_URL=https://api.example.com    # e.g. http://api:8000
- API_AUTH_TOKEN=...                      # admin/poller token (server/renderer only)

# ElevenLabs TTS (server/renderer only)
- ELEVENLABS_API_KEY=...
- ELEVENLABS_VOICE_ID=...                 # REQUIRED (select your voice)
- ELEVENLABS_MODEL_ID=eleven_multilingual_v2   # optional, defaults as set
- TTS_CACHE_DIR=/content/tts_cache        # optional, for reuse & cost control
- TTS_RATE_LIMIT_RPS=3                    # polite backoff

# Whisper ASR (server/renderer only)
- WHISPER_MODEL=base                      # tiny|base|small|medium|large
- WHISPER_DEVICE=cpu                      # cpu|cuda
- SUBTITLES_FORMAT=srt                    # srt|vtt
- SUBTITLES_BURN_IN=false                 # if true, burn into video; else sidecar

# Web (Next.js) — NEVER expose admin tokens to the browser
- NEXT_PUBLIC_API_BASE_URL=http://localhost:8000   # public base; no secrets
- ADMIN_API_TOKEN=...                    # server-only; attached by Route Handlers

Browser → Web server → API. **No direct browser → API calls that require admin auth.**

==============================================================================
Renderer Worker Contract (via API)
- Claim: POST `/api/render-jobs/{{id}}/claim` → {{"lease_expires_at": "..."}}
- Heartbeat: POST `/api/render-jobs/{{id}}/heartbeat`
- Status: POST `/api/render-jobs/{{id}}/status` body:
  - status: rendering|rendered|errored
  - artifact_path?: string (absolute container path)
  - bytes?: int
  - duration_ms?: int
  - error_class?: string
  - error_message?: string
  - stderr_snippet?: string

Queue listing (poll): GET `/api/render-jobs?status=queued&limit=N`

==============================================================================
Renderer Workflow (per job)
1) **Claim & Lease** → log `claim`; set job `rendering`.
2) **TTS** (ElevenLabs) → generate `{TMP_DIR}/{{job_id}}/vo.wav`; cache to `TTS_CACHE_DIR` keyed by hash(storyId, partId, voice, text).
3) **ASR** (Whisper) → transcription & timestamps from `vo.wav` → `{TMP_DIR}/{{job_id}}/part.srt`.
4) **Music select** → deterministic track from `MUSIC_DIR` (policy: named:<file> | first | random). Default: **first** sorted `*.mp3`.
5) **Mixdown** (ffmpeg filtergraph) → VO at 0 dB, music ducked −12 dB when VO present; output `mix.wav` or inline map.
6) **Mux** (ffmpeg) → frames/images (if used) + `mix` audio → MP4. Explicit `-map` and `-shortest`. Atomic write to `OUTPUT_DIR`.
7) **Finalize** → POST `rendered` with metadata; on failure POST `errored` with exit code + stderr snippet.

==============================================================================
Logging (single-line JSON, unbuffered)
Fields: service=renderer, event, job_id, story_id, part_id, elapsed_ms, etc.
Events: start, poll, claim, tts, asr, preflight, ffmpeg_cmd (debug), rendering (heartbeat), done, error.
On `DEBUG=true`, set `FFREPORT=file=/tmp/ffreport-{{job_id}}.log:level=32` and log its path.

==============================================================================
Security
- API_AUTH_TOKEN, ELEVENLABS_API_KEY never printed or shipped to clients.
- Next.js Web must proxy admin calls through server Route Handlers; client bundles contain **no secrets**.
- Validate all state transitions server-side; return 409 on invalid transitions.

==============================================================================
Acceptance (global)
- Renderer produces MP4s with VO + (optional) music; sidecar or burned subtitles; API reflects `rendered` with metadata.
- No browser makes privileged calls; admin token used server-side only.
- Logs are structured, unbuffered, and include correlation IDs.
- Atomic output writes and temp cleanup are guaranteed.
