from __future__ import annotations

"""Backfill helpers for the Reddit ingestion service.

This module provides utilities to fetch historical Reddit posts in time
windows.  Large windows are recursively split when the Reddit API indicates
that more results may be available (approaching the API's page limit).

After successfully processing a batch the ``reddit_fetch_state`` table is
updated to record the earliest timestamp seen for each subreddit.  An
orchestrator function is also provided which repeatedly walks backwards in
time until no results remain or a caller supplied ``earliest_target`` is
reached.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import Column, DateTime, MetaData, Table, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, insert as pg_insert

from .client import RedditClient
from .monitoring import (
    DUPLICATE_POSTS,
    INSERTED_POSTS,
    PROCESSING_LATENCY,
    REJECTED_POSTS,
)
from .normalizer import normalize_post
from .storage import insert_post, record_rejection, run_with_session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ``reddit_fetch_state`` table (minimal definition for updates)
# ---------------------------------------------------------------------------
metadata = MetaData()
reddit_fetch_state = Table(
    "reddit_fetch_state",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("subreddit", Text, unique=True, nullable=False),
    Column("backfill_earliest_utc", DateTime(timezone=True)),
    Column("mode", Text, nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _update_fetch_state(session, subreddit: str, earliest: datetime) -> None:
    """Upsert ``reddit_fetch_state.backfill_earliest_utc`` for subreddit."""

    stmt = pg_insert(reddit_fetch_state).values(
        id=uuid.uuid4(),
        subreddit=subreddit,
        backfill_earliest_utc=earliest,
        mode="backfill",
        updated_at=func.now(),
    ).on_conflict_do_update(
        index_elements=[reddit_fetch_state.c.subreddit],
        set_={
            "backfill_earliest_utc": earliest,
            "mode": "backfill",
            "updated_at": func.now(),
        },
    )
    session.execute(stmt)


def _process_posts(subreddit: str, posts: List[dict]) -> Tuple[int, Optional[datetime]]:
    """Normalize and store posts returning count and earliest timestamp."""

    fetched = len(posts)
    start = time.time()

    def op(session):
        inserted = 0
        duplicates = 0
        rejected = 0
        earliest_dt: Optional[datetime] = None
        for post in posts:
            normalized, reason = normalize_post(post)
            created_dt = datetime.fromtimestamp(int(post.get("created_utc", 0)), tz=timezone.utc)
            if normalized:
                payload = {
                    "reddit_id": post.get("name") or f"t3_{post.get('id')}",
                    "subreddit": subreddit,
                    "title": normalized.title,
                    "author": post.get("author"),
                    "url": post.get("url"),
                    "created_utc": created_dt,
                    "is_self": bool(post.get("is_self") or post.get("selftext")),
                    "selftext": normalized.body,
                    "nsfw": normalized.nsfw,
                    "language": normalized.language,
                    "upvotes": int(post.get("ups") or post.get("score") or 0),
                    "num_comments": int(post.get("num_comments") or 0),
                    "hash_title_body": normalized.hash_title_body,
                }
                if insert_post(session, payload):
                    inserted += 1
                    if earliest_dt is None or created_dt < earliest_dt:
                        earliest_dt = created_dt
                else:
                    duplicates += 1
            else:
                rejected += 1
                # Record why the post was rejected for auditing
                record_rejection(
                    session,
                    post.get("name") or post.get("id") or "",
                    subreddit,
                    reason or "unknown",
                    post,
                )
        if inserted and earliest_dt:
            _update_fetch_state(session, subreddit, earliest_dt)
        return inserted, duplicates, rejected, earliest_dt

    inserted, duplicates, rejected, earliest_dt = run_with_session(op)
    duration = time.time() - start
    logger.info(
        "process_posts",
        extra={
            "subreddit": subreddit,
            "fetched": fetched,
            "inserted": inserted,
            "duplicates": duplicates,
            "rejected": rejected,
            "duration": duration,
        },
    )
    PROCESSING_LATENCY.labels(subreddit=subreddit).observe(duration)
    INSERTED_POSTS.labels(subreddit=subreddit).inc(inserted)
    DUPLICATE_POSTS.labels(subreddit=subreddit).inc(duplicates)
    REJECTED_POSTS.labels(subreddit=subreddit).inc(rejected)
    return inserted, earliest_dt


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def backfill_by_window(
    subreddit: str,
    start_utc: int,
    end_utc: int,
    *,
    client: RedditClient | None = None,
    limit: int = 100,
    split_threshold: float = 0.9,
) -> Tuple[int, Optional[datetime]]:
    """Fetch and store posts for ``subreddit`` within ``[start_utc, end_utc]``.

    If the number of results approaches the API limit the window is recursively
    split to avoid missing posts.  Returns the number of inserted posts and the
    earliest ``created_utc`` encountered (as a timezone aware ``datetime``).
    """

    client = client or RedditClient()
    posts, _ = client.fetch_posts_by_time_window(subreddit, start_utc, end_utc, limit=limit)

    if len(posts) >= int(limit * split_threshold) and end_utc - start_utc > 1:
        mid = (start_utc + end_utc) // 2
        count1, early1 = backfill_by_window(
            subreddit, start_utc, mid, client=client, limit=limit, split_threshold=split_threshold
        )
        count2, early2 = backfill_by_window(
            subreddit, mid + 1, end_utc, client=client, limit=limit, split_threshold=split_threshold
        )
        earliest = min(
            [dt for dt in (early1, early2) if dt is not None],
            default=None,
        )
        return count1 + count2, earliest

    return _process_posts(subreddit, posts)


@dataclass
class BackfillResult:
    inserted: int
    earliest: Optional[datetime]


def orchestrate_backfill(
    subreddit: str,
    *,
    earliest_target_utc: Optional[int] = None,
    client: RedditClient | None = None,
    window_seconds: int = 7 * 24 * 60 * 60,
) -> int:
    """Backfill ``subreddit`` moving backwards until ``earliest_target_utc``.

    Returns the total number of inserted posts.
    """

    client = client or RedditClient()
    total_inserted = 0
    end = int(datetime.now(tz=timezone.utc).timestamp())

    while True:
        start = end - window_seconds
        if earliest_target_utc is not None and start < earliest_target_utc:
            start = earliest_target_utc
        inserted, earliest = backfill_by_window(
            subreddit, start, end, client=client
        )
        total_inserted += inserted

        if inserted == 0 or earliest is None:
            break

        end = int(earliest.timestamp()) - 1
        if earliest_target_utc is not None and end <= earliest_target_utc:
            break

    return total_inserted


__all__ = ["backfill_by_window", "orchestrate_backfill", "BackfillResult"]
