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

import typer
from sqlalchemy import func, select

from .backfill import orchestrate_backfill
from .incremental import fetch_incremental
from .storage import reddit_posts, run_with_session

app = typer.Typer(add_completion=False, help="Reddit ingestion commands")


def _parse_subreddits(value: str) -> List[str]:
    """Split a comma separated list of subreddits."""

    return [s.strip() for s in value.split(",") if s.strip()]


@app.command()
def backfill(
    subreddits: str = typer.Option(
        ..., "--subreddits", help="Comma separated list of subreddits"
    ),
    earliest: datetime = typer.Option(
        ..., "--earliest", formats=["%Y-%m-%d"], help="Earliest date (UTC) to backfill"
    ),
) -> None:
    """Backfill historical posts for ``subreddits``."""

    subs = _parse_subreddits(subreddits)
    earliest_ts = int(earliest.replace(tzinfo=timezone.utc).timestamp())
    for sub in subs:
        typer.echo(f"Backfilling {sub} starting from {earliest.date()}...")
        inserted = orchestrate_backfill(sub, earliest_target_utc=earliest_ts)
        typer.echo(f"Inserted {inserted} posts for r/{sub}")


@app.command()
def incremental(
    subreddits: str = typer.Option(
        ..., "--subreddits", help="Comma separated list of subreddits"
    )
) -> None:
    """Fetch new posts for ``subreddits``."""

    subs = _parse_subreddits(subreddits)
    for sub in subs:
        typer.echo(f"Fetching new posts for {sub}...")
        inserted = fetch_incremental(sub)
        typer.echo(f"Inserted {inserted} posts for r/{sub}")


@app.command()
def verify(
    subreddit: str = typer.Option(..., "--subreddit", help="Subreddit to verify")
) -> None:
    """Verify stored posts for ``subreddit``."""

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
