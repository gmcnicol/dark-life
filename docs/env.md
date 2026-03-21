# Environment Variables

This project uses the following environment variables. Copy `.env.example` to `.env` and adjust as needed.

## Global (renderer/web/api)
- `CONTENT_DIR` – directory with static content assets
- `MUSIC_DIR` – directory containing background music tracks
- `OUTPUT_DIR` – path where rendered videos are written
- `TMP_DIR` – temporary working directory for renders
- `LOG_LEVEL` – log verbosity (`debug`, `info`, `warn`, `error`)
- `JSON_LOGS` – emit logs as single-line JSON when `true`
- `DEBUG` – enable verbose debugging output
- `JOB_TIMEOUT_SEC` – maximum seconds a job may run
- `MAX_CONCURRENT` – parallel jobs allowed per worker
- `MAX_CLAIM` – maximum jobs to claim per polling cycle
- `POLL_INTERVAL_MS` – poll interval for queued work
- `LEASE_SECONDS` – lease duration for claimed jobs

## Database / compose
- `POSTGRES_USER` – Postgres user for Docker Compose
- `POSTGRES_PASSWORD` – Postgres password for Docker Compose
- `POSTGRES_DB` – Postgres database name for Docker Compose
- `DATABASE_URL` – SQLAlchemy connection string
- `REDIS_URL` – Redis URL for legacy queue consumers and local tooling

## API access
- `API_BASE_URL` – base URL of the API service
- `API_AUTH_TOKEN` – bearer token for API requests

## ElevenLabs TTS
- `ELEVENLABS_API_KEY` – ElevenLabs authentication key
- `ELEVENLABS_VOICE_ID` – voice to synthesize
- `ELEVENLABS_MODEL_ID` – optional model identifier
- `TTS_CACHE_DIR` – cache directory for generated audio
- `TTS_RATE_LIMIT_RPS` – polite request rate limit
- `TTS_SPEAKING_STYLE` – speaking style intensity (default `0`)
- `TTS_SPEAKING_SPEED` – speaking speed multiplier (default `1.0`)

## Whisper ASR
- `WHISPER_MODEL` – Whisper model size
- `WHISPER_DEVICE` – device for inference (`cpu` or `cuda`)
- `SUBTITLES_FORMAT` – subtitle format (`srt` or `vtt`)
- `SUBTITLES_BURN_IN` – burn subtitles into video when `true`
- `OPENAI_API_KEY` – OpenAI API key for Whisper API
- `OPENAI_SCRIPT_MODEL` – OpenAI model used for script adaptation
- `OPENAI_CRITIC_MODEL` – OpenAI model used for script critique
- `OPENAI_ANALYST_MODEL` – OpenAI model used for batch analysis
- `REFINEMENT_POLL_INTERVAL_SEC` – polling interval for refinement jobs
- `REFINEMENT_MAX_CONCURRENT` – maximum concurrent refinement jobs
- `REFINEMENT_LEASE_SECONDS` – lease duration for refinement claims
- `REFINEMENT_DEFAULT_BATCH_SIZE` – default candidate batch size
- `REFINEMENT_DEFAULT_SHORTLIST_SIZE` – default shortlist size

## Web (Next.js)
- `ADMIN_API_TOKEN` – server-only token for admin API calls; normally set to the same value as `API_AUTH_TOKEN`

## Reddit ingestion
- `REDDIT_CLIENT_ID` – Reddit API client id
- `REDDIT_CLIENT_SECRET` – Reddit API client secret
- `REDDIT_USER_AGENT` – Reddit API user agent
- `REDDIT_DEFAULT_SUBREDDITS` – comma-separated default subreddit list. Default order:
  `Odd_directions,shortscarystories,nosleep,stayawake,Ruleshorror,libraryofshadows,JustNotRight,TheCrypticCompendium,SignalHorrorFiction,scarystories,SLEEPSPELL,TwoSentenceHorror`
- `BACKFILL_USE_CLOUDSEARCH` – use cloudsearch windows during backfill
- `BACKFILL_MAX_PAGES` – maximum pages fetched during backfill
- `DEBUG_INGEST_SAMPLE` – log sample titles during ingest when `true`

## Scheduler
- `SCHEDULER_INTERVAL_SEC` – scheduler polling interval
- `SCHEDULER_ENABLE_REDDIT` – enable recurring Reddit ingestion
- `SCHEDULER_ENABLE_WEEKLY` – enable weekly compilation creation

## Uploads
- `YOUTUBE_CLIENT_SECRETS_FILE` – path to YouTube OAuth client secrets
- `YOUTUBE_TOKEN_FILE` – path to stored YouTube OAuth token

## Secret Consumption
- `API_AUTH_TOKEN` – attached to renderer API calls in [`services/renderer/poller.py`](../services/renderer/poller.py)
- `ADMIN_API_TOKEN` – required by API admin endpoints such as [`apps/api/reddit_admin.py`](../apps/api/reddit_admin.py) and used by web route handlers via [`apps/web/src/app/api/admin/fetch.ts`](../apps/web/src/app/api/admin/fetch.ts)
- `ELEVENLABS_API_KEY` – consumed by `services/renderer/tts.py`
- `OPENAI_API_KEY` – used by `services/renderer/subtitles.py`
