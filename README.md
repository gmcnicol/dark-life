# dark-life

Self-hosted pipeline for turning creepy Reddit stories into first-person short-form videos and weekly YouTube compilations.

## Canonical stack

- `apps/api`: FastAPI workflow and worker contracts
- `apps/web`: Next.js operator UI
- `services/renderer`: render worker
- `services/scheduler`: recurring ingestion and weekly compilation creation
- `services/reddit_ingestor`: Reddit ingestion

Legacy runtimes such as the old Flask app and `video_renderer` stack have been removed from the active path.

## Quick start

1. Copy `.env.sample` to `.env` and fill in at least:
   - `API_AUTH_TOKEN`
   - `ELEVENLABS_API_KEY`
   - `ELEVENLABS_VOICE_ID`
   - `OPENAI_API_KEY` if you want OpenAI-backed script adaptation or Whisper API transcription
2. Install dependencies:
   - `uv sync`
   - `pnpm install`
3. Start the stack:
   - `make migrate`
   - `make up`
   - `make renderer`
4. Open:
   - Web UI: [http://localhost:3000](http://localhost:3000)
   - API health: [http://localhost:8000/readyz](http://localhost:8000/readyz)

## Manual testing

The detailed operator runbook lives at [docs/manual-testing-runbook.md](/Users/gareth/src/dark-life/docs/manual-testing-runbook.md).

## Useful commands

- `make logs`
- `make renderer-logs`
- `make ingest`
- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web test -- --runInBand`
- `uv run python -m pytest -q`
