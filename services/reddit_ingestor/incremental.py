"""Incremental fetching utilities for new Reddit posts.

This module loads the last processed state from the ``reddit_fetch_state``
table and then walks the ``new`` listing for each subreddit until posts older
than the stored checkpoint are encountered. After each successful batch of
inserted posts the fetch state is updated with the most recent post's
``fullname`` and ``created_utc`` allowing subsequent runs to resume from the
correct location.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import Column, DateTime, MetaData, Table, Text, func, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, insert as pg_insert

from .client import RedditClient
from .normalizer import normalize_post
from .storage import insert_post, record_rejection, run_with_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ``reddit_fetch_state`` table (minimal definition for updates/reads)
# ---------------------------------------------------------------------------
metadata = MetaData()
reddit_fetch_state = Table(
    "reddit_fetch_state",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("subreddit", Text, unique=True, nullable=False),
    Column("last_fullname", Text),
    Column("last_created_utc", DateTime(timezone=True)),
    Column("mode", Text, nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_fetch_state(subreddit: str) -> Tuple[Optional[str], Optional[datetime]]:
    """Return ``(last_fullname, last_created_utc)`` for ``subreddit``."""

    def op(session):
        stmt = select(
            reddit_fetch_state.c.last_fullname, reddit_fetch_state.c.last_created_utc
        ).where(reddit_fetch_state.c.subreddit == subreddit)
        row = session.execute(stmt).one_or_none()
        if row:
            return row[0], row[1]
        return None, None

    return run_with_session(op)


def _update_fetch_state(session, subreddit: str, fullname: str, created: datetime) -> None:
    """Upsert ``last_fullname`` and ``last_created_utc`` for ``subreddit``."""

    stmt = pg_insert(reddit_fetch_state).values(
        id=uuid.uuid4(),
        subreddit=subreddit,
        last_fullname=fullname,
        last_created_utc=created,
        mode="incremental",
        updated_at=func.now(),
    ).on_conflict_do_update(
        index_elements=[reddit_fetch_state.c.subreddit],
        set_={
            "last_fullname": fullname,
            "last_created_utc": created,
            "mode": "incremental",
            "updated_at": func.now(),
        },
    )
    session.execute(stmt)


def _process_posts(subreddit: str, posts: List[dict]) -> Tuple[int, Optional[str], Optional[datetime]]:
    """Normalize and store posts returning count and newest post info."""

    def op(session):
        inserted = 0
        newest_fullname: Optional[str] = None
        newest_dt: Optional[datetime] = None
        for post in posts:
            normalized, reason = normalize_post(post)
            created_dt = datetime.fromtimestamp(int(post.get("created_utc", 0)), tz=timezone.utc)
            fullname = post.get("name") or f"t3_{post.get('id')}"
            if normalized:
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
                }
                if insert_post(session, payload):
                    inserted += 1
                    if newest_dt is None or created_dt > newest_dt:
                        newest_dt = created_dt
                        newest_fullname = fullname
            else:
                record_rejection(
                    session,
                    fullname,
                    subreddit,
                    reason or "unknown",
                    post,
                )
        if inserted and newest_fullname and newest_dt:
            _update_fetch_state(session, subreddit, newest_fullname, newest_dt)
        return inserted, newest_fullname, newest_dt

    return run_with_session(op)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_incremental(
    subreddit: str,
    *,
    client: RedditClient | None = None,
    limit: int = 100,
) -> int:
    """Fetch and store new posts for ``subreddit``.

    Posts are pulled from the ``new`` listing and processed until a post older
    than the recorded ``last_created_utc`` (or matching ``last_fullname``) is
    encountered. Returns the number of inserted posts.
    """

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

