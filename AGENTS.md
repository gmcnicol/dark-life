# AGENTS.md — Dark Life POC E2E (Tonight's Focus)

## Goal
By end of day: run locally on Linux → create/edit a story in the web app → fetch/select images → split into ~60s parts → enqueue → renderer outputs vertical MP4s with burned subtitles → uploader posts one part per day (start YouTube).  
No optional features — just the minimal happy path.

---

## PHASE 0 — Verify Bring-up
- [x] `docker compose up --build` runs Postgres, Redis, FastAPI (:8000), Next.js (:3000).
- [x] `.env` has DB, Redis, image API key, YouTube creds.
- [x] Renderer & uploader share the same `/output` volume.

---

## PHASE 1 — Image Fetch & Selection (UI ↔ API)
- [x] Implement `POST /api/stories/{id}/fetch-images` → hits Pexels/Pixabay → stores candidates in `assets` table (selected=false, rank=null).
- [x] Implement `GET /api/stories/{id}/images` → returns candidates.
- [x] Implement `PATCH /api/stories/{id}/images/{assetId}` → toggle selected/rank.
- [x] Web UI "Images" tab:
    - Fetch images button.
    - Grid of thumbnails, selectable.
    - Drag-sort to set rank.

---

## PHASE 2 — Split Story into Parts (~60s each)
- [x] Implement `POST /api/stories/{id}/split?target_seconds=60`:
    - Estimate words per 60s.
    - Split on sentence boundaries.
    - Store in `story_parts` table.
- [x] Web UI “Parts” tab lists all parts after split.

---

## PHASE 3 — Enqueue Series & Render
- [x] Implement `POST /api/stories/{id}/enqueue-series`:
    - Preconditions: ≥1 selected image.
    - If no parts, auto-run split.
    - For each part, create a `render_part` job with:
        - part_index
        - selected image IDs
        - text for narration
        - subtitle=true
- [x] Renderer worker:
    - Poll queued `render_part` jobs.
    - Download/copy selected images.
    - Generate placeholder narration (TTS optional).
    - Whisper subtitles from narration.
    - FFmpeg slideshow: vertical 1080x1920, crossfade images, burn subtitles.
    - Output to `output/videos/{slug}_pXX.mp4`.
    - Mark job success.

---

## PHASE 4 — Uploader (YouTube Shorts POC)
- [x] Script `services/uploader/upload_youtube.py`:
    - Find earliest rendered, unuploaded part.
    - Upload to YouTube Shorts (vertical ≤ 60s).
    - Record in `uploads` table.
- [x] Scheduler script `cron_upload.py`:
    - Run uploader once per execution.
    - Add to README: daily cron example.

---

## PHASE 5 — Smoke Test
- [x] Add `scripts/smoke_e2e.py`:
    1. Create story (API).
    2. Fetch/select images.
    3. Split.
    4. Enqueue series.
    5. Poll jobs until all parts rendered.
    6. Run uploader (dry-run OK).
- [ ] Make target: `make smoke`.

---

## Acceptance
From fresh clone + .env:
1. `docker compose up --build` (API, web, DB, Redis running)
2. `make renderer` in another terminal
3. Web: create story, fetch/select images, split, enqueue
4. Renderer outputs vertical MP4(s) with subtitles
5. `make uploader` uploads one part
6. `make smoke` passes

---
