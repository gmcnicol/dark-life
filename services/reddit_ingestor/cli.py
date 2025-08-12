"""Command line entry points for Reddit ingestion."""

from typing import List
import os

import typer

from .incremental import fetch_incremental

app = typer.Typer(add_completion=False, help="Reddit ingestion commands")


@app.callback()
def main() -> None:
    """Reddit ingestion commands."""


def _subreddits_from_env() -> List[str]:
    value = os.getenv("REDDIT_DEFAULT_SUBREDDITS", "")
    subs = [s.strip() for s in value.split(",") if s.strip()]
    if not subs:
        typer.echo(
            "REDDIT_DEFAULT_SUBREDDITS env var must specify subreddits", err=True
        )
        raise typer.Exit(code=10)
    return subs


@app.command()
def incremental() -> None:
    """Fetch new posts for default subreddits."""

    subs = _subreddits_from_env()
    for sub in subs:
        typer.echo(f"Fetching new posts for {sub}...")
        inserted = fetch_incremental(sub)
        typer.echo(f"Inserted {inserted} posts for r/{sub}")


if __name__ == "__main__":  # pragma: no cover
    app()
