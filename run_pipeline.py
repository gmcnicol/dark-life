"""Simple pipeline runner orchestrating the dark-life scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
import typer

load_dotenv()

app = typer.Typer(add_completion=False)


@app.command()
def main() -> None:
    """Run the full content pipeline."""
    subprocess.run([sys.executable, "scripts/fetch_reddit.py"], check=True)
    subprocess.run([sys.executable, "scripts/generate_voiceover.py"], check=True)
    subprocess.run([sys.executable, "scripts/generate_subtitles.py"], check=True)
    for story in sorted(Path("content/stories").glob("*.md")):
        story_id = story.stem.split("_", 1)[-1]
        subprocess.run(
            [
                sys.executable,
                "scripts/create_slideshow.py",
                "--story_id",
                story_id,
            ],
            check=True,
        )
    subprocess.run([sys.executable, "scripts/update_dashboard.py"], check=True)


if __name__ == "__main__":  # pragma: no cover
    app()

