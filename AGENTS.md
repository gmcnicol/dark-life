AGENTS.md

Project: dark-life — Web + API refactor

Goal
-----
Refactor the repo into a clean monorepo with:
1) A Python API that manages stories, assets, and workflow (DB-backed).
2) A Next.js web app that talks to the API, providing a modern, slick editing suite for stories, with auto-fetched images to select from.
3) Compatibility with the existing renderer/uploader services via events/jobs.
4) Database-first design for storing stories, images, selections, and job statuses.

High-Level Architecture
-----------------------
monorepo/
├── apps/
│   ├── api/                 # Python FastAPI service (stories/asset mgmt)
│   └── web/                 # Next.js app (App Router) with modern UI
├── services/
│   ├── renderer/            # (existing) video creation service
│   └── uploader/            # (existing) scheduled uploaders
├── packages/
│   ├── shared-types/        # OpenAPI-derived TS types, shared constants
│   └── ui/                  # (optional) shared UI lib for web app
├── infra/
│   ├── docker-compose.yml   # Postgres + Redis + local stack
│   ├── migrations/          # Alembic migrations for API DB
│   └── devcontainer/        # optional
└── .env, Makefile, etc.

Stacks
------
API:
- FastAPI (Python 3.11+)
- SQLAlchemy or SQLModel + Alembic
- Postgres (prod) / SQLite (dev ok) + Redis (queues)
- Pexels/Pixabay APIs for image search (pluggable)
- Pydantic v2
- Auth: simple token first; add OAuth later if needed
- OpenAPI schema export to generate TS types

Web:
- Next.js (App Router) + TypeScript
- TailwindCSS + shadcn/ui + Radix
- React Query (TanStack Query) against API
- Zod for client-side validation
- Super slick modern UI (clean, minimal, keyboard-first editing, dark mode)
- Image picker with live search from API, selectable + reorderable
- Editor: Markdown + side-by-side preview or rich text; autosave

Data Model (initial)
--------------------
stories:
- id (uuid PK)
- slug (unique)
- title (string)
- subreddit (string, optional)
- source_url (string, optional)
- status (enum: draft|approved|ready|rendered|uploaded)
- body_md (text)               # markdown content
- body_plain (text, computed optional)
- language (string, default 'en')
- created_at, updated_at (timestamps)

assets:
- id (uuid PK)
- story_id (uuid FK -> stories)
- type (enum: image|audio|video)
- provider (enum: pexels|pixabay|unsplash|local|other)
- remote_url (string)
- local_path (string, optional)
- width, height (int, optional)
- selected (bool)              # true if chosen for the final render
- rank (int)                   # order in slideshow
- meta (jsonb)                 # provider payload
- created_at

jobs:
- id (uuid PK)
- story_id (uuid FK -> stories)
- kind (enum: render|upload)
- status (enum: queued|running|success|failed)
- payload (jsonb)
- result (jsonb)
- created_at, updated_at

captions (optional future):
- id (uuid PK)
- story_id (uuid FK)
- srt_path (string)
- ass_path (string)
- model (string)
- created_at

API (initial endpoints)
-----------------------
Stories:
- GET   /api/stories?status=&q=&page=&limit=
- POST  /api/stories                # create new (manual or from URL)
- GET   /api/stories/{id}
- PATCH /api/stories/{id}           # update title/body/status etc.
- DELETE /api/stories/{id}

Story Utilities:
- POST /api/stories/{id}/fetch-images   # triggers provider searches by keywords
- GET  /api/stories/{id}/images         # list candidate/selected images
- PATCH /api/stories/{id}/images/{asset_id}   # mark selected, set rank
- POST /api/stories/{id}/enqueue-render # creates a render job (status -> ready)

Assets:
- POST /api/assets/upload (for manual image upload)
- GET  /api/assets/{id}
- DELETE /api/assets/{id}

Jobs:
- GET  /api/jobs?story_id=&kind=&status=
- POST /api/jobs (internal use)
- GET  /api/jobs/{id}

Search Providers (server-side)
------------------------------
- Pexels: use API key; query from extracted nouns/keywords (basic NLP or regex)
- Pixabay: fallback
- (Pluggable) Unsplash if licensing OK for your use-case

Workflows
---------
1) Ingest/Author:
   - Create story (paste Reddit URL or paste text)
   - Edit and refine in web editor (autosave)
2) Image sourcing:
   - Click “Auto-fetch images” -> API hits providers by keywords
   - Review grid, select images, drag to order
3) Ready to Render:
   - Click “Queue for Render” -> API creates render job in jobs table
   - renderer service consumes job -> outputs mp4 and writes manifest
4) Upload:
   - uploader service scans manifests on schedule -> posts to platforms

Non-Functional
--------------
- All service code linted/formatted
- API typed; generate OpenAPI and TS client/types in packages/shared-types
- .env.sample with all required secrets
- Docker dev up in one command (DB + Redis + services)
- Minimal logs + health endpoints
- Basic auth (static token) initially

Environment Variables (sample)
------------------------------
# API
API_PORT=8000
DATABASE_URL=postgresql+psycopg://user:pass@postgres:5432/darklife
REDIS_URL=redis://redis:6379/0
PEXELS_API_KEY=...
PIXABAY_API_KEY=...

# WEB
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# RENDERER/UPLOADER (existing)
ELEVENLABS_API_KEY=...
INSTAGRAM_USERNAME=...
INSTAGRAM_PASSWORD=...
...

Quality Bar for Web UI
----------------------
- App Router + server actions where appropriate
- shadcn/ui + Tailwind with tasteful, minimal styling
- Keyboard shortcuts: save (Cmd/Ctrl+S), approve (A), queue render (R)
- Drag-and-drop for image ordering; immediate visual feedback
- Form validation with Zod; error toasts; optimistic updates
- Dark mode default

Deliverables
------------
- apps/api FastAPI app with DB + migrations + endpoints above
- apps/web Next.js app with:
  - Stories list (filter/search)
  - Story editor (title, body MD, autosave)
  - Image discovery tab (auto-fetch, select, reorder)
  - CTA to queue render (calls API)
- packages/shared-types generated from OpenAPI
- infra/docker-compose to run Postgres + Redis + both apps
- docs: local dev guide + env samples

-------------------------------------------------------------------------------

TASK LIST (for Codex)
=====================

Task 01 — Monorepo skeleton
- Create monorepo folders: apps/api, apps/web, packages/shared-types, infra
- Add root-level tooling: Makefile (or taskfile), .editorconfig, .gitignore
- Create infra/docker-compose.yml with services: postgres, redis, api, web
- Provide .env.sample at root; wire env loading for api/web

Task 02 — API bootstrap (FastAPI + DB)
- Scaffold FastAPI app in apps/api with uvicorn entrypoint
- Add SQLAlchemy/SQLModel + Alembic migrations
- Implement models: Story, Asset, Job
- Implement initial migrations creating tables
- Add health endpoint GET /health
- Add config loader (pydantic-settings)

Task 03 — API: stories endpoints
- Implement CRUD: GET collection, POST, GET by id, PATCH, DELETE
- body_md validated (non-empty), status default draft
- Add slug generation; unique constraint
- Return OpenAPI schema export (openapi.json)

Task 04 — API: provider search + image assets
- Implement /api/stories/{id}/fetch-images:
  - Extract keywords from title + body (simple regex list; leave NLP hook)
  - Query Pexels (and fallback Pixabay) with API keys
  - Store results as Asset rows (type=image, provider, remote_url, meta)
- Implement /api/stories/{id}/images:
  - GET list (selected first, then by created/rank)
  - PATCH asset selected/rank updates
- Add rate limiting/backoff for providers

Task 05 — API: jobs + enqueue render
- Implement jobs table CRUD (minimal)
- Implement /api/stories/{id}/enqueue-render that:
  - Validates: story status in (approved|ready), has selected images
  - Creates Job(kind=render, status=queued, payload with asset IDs)
- Add Redis pub/sub OR write a jobs:queued row (renderer polls)
- Update story status to ready when enqueued

Task 06 — Generate TS types client
- From API OpenAPI, generate TypeScript types + simple client into packages/shared-types
- Publish locally via workspace symlink (pnpm or npm workspaces)
- Web app imports these types

Task 07 — Web bootstrap (Next.js)
- Create apps/web with Next.js (TypeScript, App Router)
- Install Tailwind + shadcn/ui + Radix; configure base theme (dark default)
- Setup api client (fetch wrapper) + TanStack Query provider
- Read NEXT_PUBLIC_API_BASE_URL for calls

Task 08 — Web: Stories list + CRUD
- Page: /stories lists with search, filters (status)
- Actions: create new, delete, open editor
- Use shared-types for typing
- Toasts + error handling

Task 09 — Web: Story editor (autosave)
- Page: /stories/[id]
- Inputs: title, subreddit, source_url
- Editor: markdown textarea + live preview panel
- Autosave on debounce; success/error toasts
- Status control (draft/approved)

Task 10 — Web: Image discovery + selection
- Tab/section in editor: “Images”
- Button: “Auto-fetch images” (calls API)
- Grid of results with preview, aspect badges, provider
- Select/unselect toggle; drag-and-drop reorder
- Persist selection + rank via PATCH assets endpoint
- Visual feedback for save state

Task 11 — Web: Queue render CTA
- Button “Queue for render”:
  - Confirms requirements (approved, selected images)
  - Calls enqueue-render endpoint
  - Shows job status link
- Add /jobs page to list jobs with story link + status

Task 12 — Dev UX and polish
- Keyboard shortcuts: save (Ctrl/Cmd+S), approve (A), queue render (R)
- Add skeleton states + optimistic updates
- Tighten styling (spacing, muted palette, subtle shadows)
- Add favicon/logo placeholder

Task 13 — Docs + env
- Write README for running locally (docker-compose up, then web and api)
- Provide .env.sample for all apps
- Add provider API key instructions
- Add note for existing renderer/uploader integration (jobs table contract)

Task 14 — (Optional) Renderer integration stub
- In services/renderer, add a tiny poller script that:
  - Watches jobs table for queued render jobs
  - Prints payload; mark as running -> success for demo
- Ensures E2E flow works (enqueue from web, job appears and completes)

Acceptance Criteria
-------------------
- `docker compose up` brings Postgres, Redis
- API runs on :8000, Web on :3000 (configurable)
- Can create/edit a story from Web, fetch images, select and order them
- Can enqueue a render job and see it recorded in DB
- Web UI is fast, clean, modern, dark-mode by default
- Code is typed, linted, and documented; OpenAPI -> TS types in packages/shared-types

