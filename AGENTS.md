# AGENTS.md

Project: dark-life — Reddit Ingestion Service

Goal
----
Implement a dedicated Reddit ingestion service that:
1. Backfills posts from specified subreddits as far back as possible.
2. Stores canonical references and enforces uniqueness (no duplicates).
3. Supports incremental fetches for only new posts after initial backfill.
4. Filters for language, length, NSFW, and quality.
5. Is idempotent, observable, and safe to re-run.

Deliverables
------------
- Python package: services/reddit_ingestor/
- CLI commands for backfill, incremental fetch, verification.
- Database tables + Alembic migrations.
- Configurable list of subreddits and filters.
- Logs/metrics for ingestion stats and dedup actions.

Environment Variables
---------------------
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=dark-life-ingestor/1.0
MIN_UPVOTES=0
MIN_BODY_CHARS=300
MAX_BODY_CHARS=3500
ALLOW_NSFW=false
LANG_ALLOW=en
REQUESTS_PER_MINUTE=60

Database Model
--------------
Table: reddit_posts
- id (uuid PK)
- reddit_id (text, UNIQUE)             e.g., "t3_abc123"
- subreddit (text, index)
- title (text)
- author (text)
- url (text)                            canonical Reddit URL
- created_utc (timestamptz, index)
- is_self (bool)
- selftext (text)                       raw body
- nsfw (bool)
- language (text)
- upvotes (int)
- num_comments (int)
- hash_title_body (text, index)         SHA256(title + normalized body)
- inserted_at, updated_at (timestamptz)

Unique constraints:
- reddit_id UNIQUE
- (subreddit, hash_title_body) UNIQUE

Table: reddit_fetch_state
- id (uuid PK)
- subreddit (text, UNIQUE)
- last_fullname (text, nullable)
- last_created_utc (timestamptz, nullable)
- backfill_earliest_utc (timestamptz, nullable)
- mode (text) values: 'backfill'|'incremental'
- updated_at (timestamptz)

Table: reddit_rejections (optional)
- id (uuid PK)
- reddit_id (text)
- subreddit (text)
- reason (text)
- payload (jsonb)
- created_at (timestamptz)

Tasks
-----
Task 01 — Migrations
- Create Alembic migrations for reddit_posts, reddit_fetch_state, reddit_rejections.

Task 02 — Reddit API Client
- Implement PRAW or requests-based client with:
  - “new” listing pagination (after=<fullname>) for incremental fetches.
  - Time-windowed fetch for backfill.
  - Configurable subreddits.
  - Respect rate limits and backoff.

Task 03 — Normalization & Filtering
- Language detection; skip if not LANG_ALLOW.
- Drop NSFW if ALLOW_NSFW=false.
- Enforce length MIN/MAX_BODY_CHARS.
- Normalize markdown: trim, collapse whitespace, strip boilerplate.
- Compute hash_title_body = SHA256(title + normalized_body).

Task 04 — Persistence & Deduplication
- Insert posts with ON CONFLICT DO NOTHING on reddit_id.
- Enforce (subreddit, hash_title_body) unique to avoid identical crossposts.
- Record skips in reddit_rejections.

Task 05 — Backfill Mode
- Implement backfill_by_window(subreddit, start_utc, end_utc):
  - Query posts in [start_utc, end_utc].
  - If count near API limit, split window and recurse.
  - Update reddit_fetch_state.backfill_earliest_utc.
- Orchestrator to walk backwards until earliest_target_utc or no results.

Task 06 — Incremental Mode
- Load last_fullname or last_created_utc from reddit_fetch_state.
- Fetch “new” posts until older than checkpoint.
- Update last_fullname and last_created_utc after successful batch.

Task 07 — CLI Interface
- `reddit backfill --subreddits nosleep,confession --earliest 2008-01-01`
- `reddit incremental --subreddits nosleep,confession`
- `reddit verify --subreddit nosleep` to check for duplicates or invalid data.

Task 08 — Logging & Metrics
- Log counts: fetched, inserted, duplicates, rejected, duration.
- Emit metrics for future Prometheus integration.

Task 09 — Testing
- Unit tests for normalization, deduplication, language filter.
- Integration tests for backfill and incremental flows.
- Idempotency test: re-run same batch yields zero new inserts.

Acceptance Criteria
-------------------
1. Backfill ingests oldest possible posts; earliest date stored.
2. Incremental mode only inserts posts newer than last run.
3. No duplicate reddit_id or identical title+body for same subreddit.
4. Filters applied correctly; rejects logged.
5. Service is idempotent and safe to re-run.
6. Can be scheduled to run hourly for new posts without duplicates.

Optional Stretch
----------------
- Dedup across subreddits using fuzzy match.
- Extract and store image URLs from Reddit-hosted media.
- Push new-story events to API for live updates in web app.