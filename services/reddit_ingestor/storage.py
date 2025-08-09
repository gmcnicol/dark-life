from __future__ import annotations

"""Database storage helpers for the Reddit ingestion service.

This module provides utilities to insert posts into ``reddit_posts`` while
handling duplicates via PostgreSQL's ``ON CONFLICT`` clause. It also records
rejected posts for later inspection. Lightweight helpers are included to manage
sessions and retry transient failures.
"""

import time
import uuid
from typing import Any, Callable, Dict, TypeVar

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
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, insert as pg_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

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

def run_with_session(operation: Callable[[Session], T], *, retries: int = 3, backoff: float = 0.5) -> T:
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

def insert_post(session: Session, payload: Dict[str, Any]) -> bool:
    """Insert a Reddit post into ``reddit_posts``.

    Returns ``True`` if the post was inserted, or ``False`` when a duplicate was
    detected via the ``reddit_id`` or ``(subreddit, hash_title_body)`` unique
    constraints.
    """

    values = {"id": uuid.uuid4(), **payload}
    stmt = pg_insert(reddit_posts).values(values).on_conflict_do_nothing()
    result = session.execute(stmt)
    return bool(result.rowcount)

def record_rejection(
    session: Session,
    reddit_id: str,
    subreddit: str,
    reason: str,
    payload: Dict[str, Any] | None = None,
) -> None:
    """Record a rejected post for auditing purposes."""

    stmt = reddit_rejections.insert().values(
        id=uuid.uuid4(),
        reddit_id=reddit_id,
        subreddit=subreddit,
        reason=reason,
        payload=payload,
    )
    session.execute(stmt)


__all__ = ["engine", "SessionLocal", "run_with_session", "insert_post", "record_rejection"]
