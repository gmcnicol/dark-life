from __future__ import annotations

"""Command line interface for the Reddit ingestion service.

This module exposes a small Typer based CLI with three commands:

* ``reddit backfill`` – run the backfill orchestrator for one or more
  subreddits.
* ``reddit incremental`` – fetch only new posts for the given subreddits.
* ``reddit verify`` – perform a basic verification of stored posts for a
  subreddit, checking for duplicate ``reddit_id`` or ``hash_title_body``
  entries.
"""

from datetime import datetime, timezone
from typing import List
import os

import typer
from sqlalchemy import func, select

from .backfill import orchestrate_backfill
from .incremental import fetch_incremental
from .storage import reddit_posts, run_with_session

app = typer.Typer(add_completion=False, help="Reddit ingestion commands")

DEFAULT_BACKFILL_START = datetime(2023, 1, 1, tzinfo=timezone.utc)


def _subreddits_from_env() -> List[str]:
    """Fetch default subreddits from the environment."""

    value = os.getenv("REDDIT_DEFAULT_SUBREDDITS", "")
    subs = [s.strip() for s in value.split(",") if s.strip()]
    if not subs:
        typer.echo(
            "REDDIT_DEFAULT_SUBREDDITS env var must specify subreddits", err=True
        )
        raise typer.Exit(code=10)
    return subs


@app.command()
def backfill() -> None:
    """Backfill historical posts for default subreddits."""

    subs = _subreddits_from_env()
    earliest_ts = int(DEFAULT_BACKFILL_START.timestamp())
    for sub in subs:
        typer.echo(
            f"Backfilling {sub} starting from {DEFAULT_BACKFILL_START.date()}..."
        )
        inserted = orchestrate_backfill(sub, earliest_target_utc=earliest_ts)
        typer.echo(f"Inserted {inserted} posts for r/{sub}")


@app.command()
def incremental() -> None:
    """Fetch new posts for default subreddits."""

    subs = _subreddits_from_env()
    for sub in subs:
        typer.echo(f"Fetching new posts for {sub}...")
        inserted = fetch_incremental(sub)
        typer.echo(f"Inserted {inserted} posts for r/{sub}")


@app.command()
def verify() -> None:
    """Verify stored posts for default subreddits."""

    subs = _subreddits_from_env()
    for subreddit in subs:
        typer.echo(f"Verifying {subreddit}...")

        def op(session):
            total = session.execute(
                select(func.count()).select_from(reddit_posts).where(
                    reddit_posts.c.subreddit == subreddit
                )
            ).scalar()
            dup_ids = session.execute(
                select(reddit_posts.c.reddit_id, func.count())
                .where(reddit_posts.c.subreddit == subreddit)
                .group_by(reddit_posts.c.reddit_id)
                .having(func.count() > 1)
            ).all()
            dup_hash = session.execute(
                select(reddit_posts.c.hash_title_body, func.count())
                .where(reddit_posts.c.subreddit == subreddit)
                .group_by(reddit_posts.c.hash_title_body)
                .having(func.count() > 1)
            ).all()
            return total, dup_ids, dup_hash

        total, dup_ids, dup_hash = run_with_session(op)
        typer.echo(f"Total posts: {total}")
        if dup_ids:
            typer.echo(f"Duplicate reddit_id entries: {dup_ids}")
        if dup_hash:
            typer.echo(f"Duplicate hash_title_body entries: {dup_hash}")
        if not dup_ids and not dup_hash:
            typer.echo("No duplicates found.")


if __name__ == "__main__":  # pragma: no cover
    app()
