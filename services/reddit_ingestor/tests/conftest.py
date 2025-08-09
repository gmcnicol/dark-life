import types
import sys
from importlib import reload
from pathlib import Path

import pytest


@pytest.fixture()
def ingestor_env(tmp_path, monkeypatch):
    """Prepare isolated env and database for tests."""
    # Ensure repository root is on sys.path for imports
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.append(str(repo_root))

    db_url = f"sqlite:///{tmp_path}/reddit.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("METRICS_ENABLED", "false")
    monkeypatch.setenv("MIN_BODY_CHARS", "1")
    monkeypatch.setenv("MAX_BODY_CHARS", "1000")
    monkeypatch.setenv("LANG_ALLOW", "en")
    monkeypatch.setenv("ALLOW_NSFW", "false")

    from importlib import import_module

    config_module = import_module("shared.config")
    monitoring = import_module("services.reddit_ingestor.monitoring")
    storage = import_module("services.reddit_ingestor.storage")
    backfill = import_module("services.reddit_ingestor.backfill")
    incremental = import_module("services.reddit_ingestor.incremental")
    normalizer = import_module("services.reddit_ingestor.normalizer")

    # Reload modules that depend on DATABASE_URL or other env vars
    reload(config_module)
    reload(storage)
    reload(backfill)
    reload(incremental)
    reload(normalizer)

    # Create minimal schema
    with storage.engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS reddit_posts (
                id TEXT PRIMARY KEY,
                reddit_id TEXT UNIQUE,
                subreddit TEXT NOT NULL,
                title TEXT NOT NULL,
                author TEXT,
                url TEXT NOT NULL,
                created_utc TIMESTAMP NOT NULL,
                is_self BOOLEAN NOT NULL,
                selftext TEXT,
                nsfw BOOLEAN NOT NULL,
                language TEXT,
                upvotes INTEGER NOT NULL,
                num_comments INTEGER NOT NULL,
                hash_title_body TEXT NOT NULL,
                image_urls TEXT,
                UNIQUE(subreddit, hash_title_body)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS reddit_rejections (
                id TEXT PRIMARY KEY,
                reddit_id TEXT NOT NULL,
                subreddit TEXT NOT NULL,
                reason TEXT NOT NULL,
                payload TEXT,
                created_at TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS reddit_fetch_state (
                id TEXT PRIMARY KEY,
                subreddit TEXT UNIQUE NOT NULL,
                last_fullname TEXT,
                last_created_utc TIMESTAMP,
                backfill_earliest_utc TIMESTAMP,
                mode TEXT NOT NULL,
                updated_at TIMESTAMP
            )
            """
        )
    return types.SimpleNamespace(
        storage=storage,
        backfill=backfill,
        incremental=incremental,
        normalizer=normalizer,
    )
