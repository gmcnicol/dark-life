# AGENTS.md

Project: dark-life — POC Task List

Goal
----
Deliver a minimal end-to-end proof of concept that lets us:
1. Create and edit a story in the web app.
2. Auto-fetch and select images for that story.
3. Queue the story for rendering.
4. Render a simple MP4 slideshow with narration and burned-in subtitles.
5. Upload the final MP4 to at least one platform on a schedule.

Scope
-----
We will not implement authentication, retries/DLQ, advanced attribution, or production CI/CD in this phase. This is purely to prove the workflow works from ingest to upload.

Tasks
-----

Task 01 — Stories CRUD (Web ↔ API)
- Implement `/api/stories` CRUD endpoints in FastAPI:
  - GET collection, GET by ID, POST, PATCH, DELETE.
- Connect the Next.js story editor page to these endpoints:
  - Title, subreddit, source_url, and Markdown body fields.
  - Autosave on change.
- Ensure created/edited stories persist to the DB and are returned correctly.

Task 02 — Image Auto-Fetch Flow
- Implement `/api/stories/{id}/fetch-images` endpoint:
  - Extract basic keywords from the story body/title.
  - Query Pexels (and optionally Pixabay) using API key(s).
  - Persist returned results to the `assets` table (type=image).
- Implement `/api/stories/{id}/images` GET to list all candidate/selected images.
- In the Next.js editor:
  - Show image results grid.
  - Allow select/unselect.
  - Allow drag-and-drop reorder.
  - Save selections and ranks to the API via PATCH.

Task 03 — Queue to Render
- Implement `/api/stories/{id}/enqueue-render` endpoint:
  - Validate story has selected images.
  - Add a render job to a simple jobs table (status=queued).
- Create a minimal `video_renderer/poller.py`:
  - Poll jobs table for queued jobs.
  - For each job:
    - Download images and voiceover.
    - Run FFmpeg to produce a 9:16 MP4 with:
      - Selected images crossfading every 5s.
      - Simple dark overlay.
    - Save final MP4 to `output/videos/`.
    - Update job status to `success`.

Task 04 — Captions
- Extend the renderer:
  - Run Whisper/faster-whisper on the narration MP3 to produce `.srt`.
  - Burn `.srt` into the MP4 with FFmpeg.
- Store `.srt` alongside MP4 in `output/videos/`.

Task 05 — Happy-Path Uploader
- Pick **one** platform for POC (YouTube Shorts recommended).
- Implement `video_uploader/upload_youtube.py`:
  - Read latest successful render from `output/videos/`.
  - Upload with story title as caption.
  - Log uploaded URL.
- Add a cron/scheduled runner in `video_uploader/cron_upload.py` that runs daily at a set time.

Exit Criteria
-------------
From the web app, a user can:
- Create/edit a story.
- Auto-fetch images and select them.
- Click “Queue render” and have a worker produce a final MP4 with images, narration, and burned subtitles.
- See that MP4 uploaded to one target platform automatically within 24h.

Out of Scope
------------
- Authentication/authorization.
- Retry logic or DLQ for failed jobs.
- Attribution exports.
- Production-ready infra or CI/CD.
- Multiple platforms or multi-queue orchestration.
