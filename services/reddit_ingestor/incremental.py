"""Incremental fetching utilities for new Reddit posts.

This module no longer touches the database directly.  Fetch state is persisted
through the API's ``/admin/reddit/state`` endpoint and stories are created via
``/admin/stories``.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
import os
from typing import List, Optional, Tuple, Dict

import requests

from .client import RedditClient
from .monitoring import (
    DUPLICATE_POSTS,
    INSERTED_POSTS,
    PROCESSING_LATENCY,
    REJECTED_POSTS,
)
from .normalizer import normalize_post
from .media import extract_image_urls
from .events import push_new_story
from .storage import insert_post
from shared.config import settings

logger = logging.getLogger(__name__)
MIN_UPVOTES = int(os.getenv("REDDIT_MIN_UPVOTES", "0"))


def _auth_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if settings.API_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {settings.API_AUTH_TOKEN}"
    return headers


def _load_fetch_state(subreddit: str) -> Tuple[Optional[str], Optional[datetime]]:
    if not settings.API_BASE_URL:
        return None, None
    resp = requests.get(
        f"{settings.API_BASE_URL.rstrip('/')}/admin/reddit/state",
        params={"subreddit": subreddit},
        headers=_auth_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None, None
    row = data[0]
    last_fullname = row.get("last_fullname")
    last_created = row.get("last_created_utc")
    last_dt = datetime.fromisoformat(last_created) if last_created else None
    return last_fullname, last_dt


def _update_fetch_state(subreddit: str, fullname: str, created: datetime) -> None:
    if not settings.API_BASE_URL:
        return
    payload = {
        "subreddit": subreddit,
        "last_fullname": fullname,
        "last_created_utc": created.isoformat(),
    }
    resp = requests.post(
        f"{settings.API_BASE_URL.rstrip('/')}/admin/reddit/state",
        json=payload,
        headers=_auth_headers(),
        timeout=10,
    )
    resp.raise_for_status()


def _process_posts(subreddit: str, posts: List[dict]) -> Tuple[int, Optional[str], Optional[datetime]]:
    """Normalize and store posts returning count and newest post info."""

    fetched = len(posts)
    start = time.time()

    inserted = 0
    duplicates = 0
    rejected = 0
    newest_fullname: Optional[str] = None
    newest_dt: Optional[datetime] = None

    for post in posts:
        created_dt = datetime.fromtimestamp(int(post.get("created_utc", 0)), tz=timezone.utc)
        fullname = post.get("name") or f"t3_{post.get('id')}"
        if int(post.get("ups") or post.get("score") or 0) < MIN_UPVOTES:
            rejected += 1
            continue
        normalized, _reason = normalize_post(post)
        if not normalized:
            rejected += 1
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
        if insert_post(payload):
            inserted += 1
            push_new_story(payload)
            if newest_dt is None or created_dt > newest_dt:
                newest_dt = created_dt
                newest_fullname = fullname
        else:
            duplicates += 1

    if inserted and newest_fullname and newest_dt:
        _update_fetch_state(subreddit, newest_fullname, newest_dt)

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
    return inserted, newest_fullname, newest_dt


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_incremental(
    subreddit: str,
    *,
    client: RedditClient | None = None,
    limit: int = 100,
) -> int:
    """Fetch and store new posts for ``subreddit``."""

    client = client or RedditClient()
    last_fullname, last_created = _load_fetch_state(subreddit)
    after: Optional[str] = None
    total_inserted = 0

    while True:
        posts, next_after = client.fetch_new_posts(subreddit, after=after, limit=limit)
        if not posts:
            break

        new_posts: List[dict] = []
        reached_checkpoint = False
        for post in posts:
            fullname = post.get("name") or f"t3_{post.get('id')}"
            created_dt = datetime.fromtimestamp(int(post.get("created_utc", 0)), tz=timezone.utc)
            if last_fullname and fullname == last_fullname:
                reached_checkpoint = True
                break
            if last_created and created_dt <= last_created:
                reached_checkpoint = True
                break
            new_posts.append(post)

        if not new_posts:
            break

        inserted, newest_fullname, newest_dt = _process_posts(subreddit, new_posts)
        total_inserted += inserted

        if reached_checkpoint:
            break
        after = next_after
        if after is None:
            break

    return total_inserted


__all__ = ["fetch_incremental"]
