from __future__ import annotations

"""Persistence helpers for the Reddit ingestion service.

This module stores posts either directly in the local database or, when an
``API_BASE_URL`` is configured, forwards them to the API's admin endpoint.
Older direct-DB helpers remain for test environments which set no API base URL.
"""

import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, TypeVar
from difflib import SequenceMatcher

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    JSON,
    MetaData,
    Table,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, insert as pg_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
import requests

from shared.config import settings

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Engine & Table definitions
# ---------------------------------------------------------------------------

engine = create_engine(settings.DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

metadata = MetaData()

reddit_posts = Table(
    "reddit_posts",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("reddit_id", Text, nullable=False),
    Column("subreddit", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("author", Text),
    Column("url", Text, nullable=False),
    Column("created_utc", DateTime(timezone=True), nullable=False),
    Column("is_self", Boolean, nullable=False),
    Column("selftext", Text),
    Column("nsfw", Boolean, nullable=False),
    Column("language", Text),
    Column("upvotes", Integer, nullable=False),
    Column("num_comments", Integer, nullable=False),
    Column("hash_title_body", Text, nullable=False),
    Column("image_urls", JSON),
)

reddit_rejections = Table(
    "reddit_rejections",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("reddit_id", Text, nullable=False),
    Column("subreddit", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("payload", JSON),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def run_with_session(
    operation: Callable[[Session | None], T], *, retries: int = 3, backoff: float = 0.5
) -> T:
    """Execute ``operation`` within a session with retry logic.

    Parameters
    ----------
    operation:
        Callable receiving a ``Session``. Its return value is returned from this
        function.
    retries:
        Number of retries on ``OperationalError``.
    backoff:
        Base backoff in seconds between retries. Exponential growth is applied.
    """

    if settings.API_BASE_URL:
        # No direct DB access; caller must handle persistence via API.
        return operation(None)

    attempt = 0
    while True:
        session: Session = SessionLocal()
        try:
            result = operation(session)
            session.commit()
            return result
        except OperationalError:
            session.rollback()
            attempt += 1
            if attempt >= retries:
                raise
            time.sleep(backoff * attempt)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def insert_post(session: Session | None, payload: Dict[str, Any]) -> bool:
    """Persist a Reddit post via API or direct DB insert.

    When ``settings.API_BASE_URL`` is set the payload is translated into the
    API's ``StoryIn`` schema and POSTed to ``/admin/stories``.  Otherwise the
    legacy ``reddit_posts`` table is written to directly.  Returns ``True`` when
    the post was created/updated, ``False`` for duplicates.
    """

    if settings.API_BASE_URL:
        story = {
            "external_id": payload["reddit_id"],
            "source": "reddit",
            "title": payload["title"],
            "author": payload.get("author"),
            "created_utc": int(payload["created_utc"].timestamp())
            if isinstance(payload["created_utc"], datetime)
            else int(payload["created_utc"]),
            "text": payload.get("selftext"),
            "url": payload.get("url"),
            "nsfw": payload.get("nsfw"),
            "flair": None,
            "tags": None,
        }
        headers = {}
        if settings.ADMIN_API_TOKEN:
            headers["Authorization"] = f"Bearer {settings.ADMIN_API_TOKEN}"
        resp = requests.post(
            f"{settings.API_BASE_URL.rstrip('/')}/admin/stories",
            json=story,
            headers=headers,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return True
        if resp.status_code == 409:
            return False
        resp.raise_for_status()
        return False

    values = {"id": uuid.uuid4(), **payload}
    stmt = pg_insert(reddit_posts).values(values).on_conflict_do_nothing()
    result = session.execute(stmt)
    return bool(result.rowcount)


def is_fuzzy_duplicate(
    session: Session | None,
    subreddit: str,
    title: str,
    body: str,
    *,
    threshold: float = 0.9,
) -> bool:
    """Return ``True`` if similar post exists in another subreddit.

    A simple in-memory comparison using :class:`difflib.SequenceMatcher` is
    performed against all stored posts outside of ``subreddit``.  When the
    similarity ratio meets or exceeds ``threshold`` the post is considered a
    duplicate.
    """

    if session is None:
        return False

    combined = f"{title} {body}".strip()
    if not combined:
        return False

    stmt = select(reddit_posts.c.title, reddit_posts.c.selftext).where(
        reddit_posts.c.subreddit != subreddit
    )
    for row in session.execute(stmt):
        existing = f"{row.title} {row.selftext or ''}"
        if SequenceMatcher(None, combined, existing).ratio() >= threshold:
            return True
    return False

def record_rejection(
    session: Session | None,
    reddit_id: str,
    subreddit: str,
    reason: str,
    payload: Dict[str, Any] | None = None,
) -> None:
    """Record a rejected post for auditing purposes."""
    if session is None:
        return
    stmt = reddit_rejections.insert().values(
        id=uuid.uuid4(),
        reddit_id=reddit_id,
        subreddit=subreddit,
        reason=reason,
        payload=payload,
    )
    session.execute(stmt)


__all__ = [
    "engine",
    "SessionLocal",
    "run_with_session",
    "insert_post",
    "record_rejection",
    "is_fuzzy_duplicate",
]
