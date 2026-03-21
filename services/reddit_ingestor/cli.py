"""Command line entry points for Reddit ingestion."""

from typing import List

import typer

from .incremental import fetch_incremental
from shared.config import parse_csv_list, settings

app = typer.Typer(add_completion=False, help="Reddit ingestion commands")


@app.callback()
def main() -> None:
    """Reddit ingestion commands."""


def _default_subreddits() -> List[str]:
    subs = parse_csv_list(settings.REDDIT_DEFAULT_SUBREDDITS)
    if not subs:
        typer.echo(
            "REDDIT_DEFAULT_SUBREDDITS env var must specify subreddits", err=True
        )
        raise typer.Exit(code=10)
    return subs


@app.command()
def incremental() -> None:
    """Fetch new posts for default subreddits."""

    subs = _default_subreddits()
    for sub in subs:
        typer.echo(f"Fetching new posts for {sub}...")
        inserted = fetch_incremental(sub)
        typer.echo(f"Inserted {inserted} posts for r/{sub}")


if __name__ == "__main__":  # pragma: no cover
    app()
