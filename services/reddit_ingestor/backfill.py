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
import datetime as dt
import logging
import time
import uuid
import os
from typing import List, Optional, Tuple, Dict, Any

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
from .normalize import normalize_and_filter
from .media import extract_image_urls
from .events import push_new_story
from .storage import (
    insert_post,
    is_fuzzy_duplicate,
    record_rejection,
    run_with_session,
)
from shared.config import settings

logger = logging.getLogger(__name__)
MIN_UPVOTES = int(os.getenv("REDDIT_MIN_UPVOTES", "0"))
DEFAULT_BACKFILL_START = dt.datetime(2023, 1, 1, tzinfo=timezone.utc)

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
    if session is None:
        return

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
            created_dt = datetime.fromtimestamp(int(post.get("created_utc", 0)), tz=timezone.utc)
            fullname = post.get("name") or f"t3_{post.get('id')}"
            if int(post.get("ups") or post.get("score") or 0) < MIN_UPVOTES:
                rejected += 1
                record_rejection(session, fullname, subreddit, "low_upvotes", post)
                continue
            normalized, reason = normalize_post(post)
            if normalized:
                if is_fuzzy_duplicate(session, subreddit, normalized.title, normalized.body):
                    duplicates += 1
                    record_rejection(
                        session,
                        fullname,
                        subreddit,
                        "fuzzy_duplicate",
                        post,
                    )
                    continue

                payload = {
                    "reddit_id": fullname,
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
                    "image_urls": extract_image_urls(post),
                }
                if insert_post(session, payload):
                    inserted += 1
                    push_new_story(payload)
                    if earliest_dt is None or created_dt < earliest_dt:
                        earliest_dt = created_dt
                else:
                    duplicates += 1
            else:
                rejected += 1
                # Record why the post was rejected for auditing
                record_rejection(
                    session,
                    fullname,
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


def _upsert_batch(batch: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    """Insert a batch of normalized docs, returning counts."""

    def op(session):
        inserted = 0
        duplicates = 0
        for doc in batch:
            if insert_post(session, doc):
                inserted += 1
            else:
                duplicates += 1
        return inserted, duplicates, 0

    return run_with_session(op)


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
    subreddit: str, earliest_target_utc: Optional[int] = None
) -> Dict[str, Any]:
    """Bounded backfill using ``new`` listing with optional cloudsearch windows."""

    earliest_ts = earliest_target_utc or int(DEFAULT_BACKFILL_START.timestamp())

    rc = RedditClient(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_CLIENT_SECRET,
        user_agent=settings.REDDIT_USER_AGENT,
    )

    max_pages = int(settings.BACKFILL_MAX_PAGES)
    use_cloud = bool(settings.BACKFILL_USE_CLOUDSEARCH)

    inserted = 0
    dup = 0
    rejected = 0
    newest_seen = None
    oldest_seen = None

    page_count = 0
    batch: List[Dict[str, Any]] = []
    for i, post in enumerate(rc.list_new(subreddit, limit=None), start=1):
        created_ts = int(getattr(post, "created_utc", 0))
        if newest_seen is None or created_ts > newest_seen:
            newest_seen = created_ts
        if oldest_seen is None or created_ts < oldest_seen:
            oldest_seen = created_ts

        doc = normalize_and_filter(post)
        if doc is None:
            rejected += 1
        else:
            batch.append(doc)

        if len(batch) >= 200:
            ins, d, _ = _upsert_batch(batch)
            inserted += ins
            dup += d
            batch = []

        if i % 100 == 0:
            page_count += 1
            if page_count >= max_pages or created_ts < earliest_ts:
                logger.info(
                    "stop paging: pages=%s created_ts=%s earliest_ts=%s",
                    page_count,
                    created_ts,
                    earliest_ts,
                )
                break

    if batch:
        ins, d, _ = _upsert_batch(batch)
        inserted += ins
        dup += d

    if oldest_seen and oldest_seen <= earliest_ts:
        return {
            "inserted": inserted,
            "duplicates": dup,
            "rejected": rejected,
            "oldest_seen": oldest_seen,
            "newest_seen": newest_seen,
            "note": "Reached earliest via listing",
        }

    if use_cloud:
        end_dt = dt.datetime.utcfromtimestamp(oldest_seen or int(time.time()))
        for _ in range(6):
            start_dt = end_dt - dt.timedelta(days=30)
            posts = rc.search_between(
                subreddit, int(start_dt.timestamp()), int(end_dt.timestamp())
            )
            batch = []
            for post in posts:
                created_ts = int(getattr(post, "created_utc", 0))
                if oldest_seen is None or created_ts < oldest_seen:
                    oldest_seen = created_ts
                doc = normalize_and_filter(post)
                if doc is None:
                    rejected += 1
                else:
                    batch.append(doc)
            if batch:
                ins, d, _ = _upsert_batch(batch)
                inserted += ins
                dup += d
            end_dt = start_dt
            if oldest_seen and oldest_seen <= earliest_ts:
                break

    return {
        "inserted": inserted,
        "duplicates": dup,
        "rejected": rejected,
        "oldest_seen": oldest_seen,
        "newest_seen": newest_seen,
        "note": "Bounded backfill; cloudsearch best-effort"
        if use_cloud
        else "Bounded backfill only",
    }


__all__ = [
    "backfill_by_window",
    "orchestrate_backfill",
    "BackfillResult",
    "DEFAULT_BACKFILL_START",
]
