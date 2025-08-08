"""Simple web UI for managing stories and rendering jobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from flask import Flask, redirect, render_template, request, url_for
import typer

from shared import config
from shared.reddit import fetch_top_stories

app = Flask(__name__, template_folder="templates", static_folder="static")
cli = typer.Typer()


@cli.callback()
def main() -> None:
    """CLI entry point for the web application."""
    pass


@app.route("/")
def index():
    stories = sorted(config.STORIES_DIR.glob("*.md"))
    return render_template("index.html", stories=[s.name for s in stories])


@app.post("/fetch")
def fetch():
    fetch_top_stories()
    return redirect(url_for("index"))


@app.post("/queue")
def queue_story():
    story_name = request.form.get("story")
    images = request.form.get("images", "").split()
    story_path = config.STORIES_DIR / story_name
    image_paths: List[str] = [str((config.VISUALS_DIR / img).resolve()) for img in images if img]
    job = {"story_path": str(story_path.resolve()), "image_paths": image_paths}
    config.RENDER_QUEUE_DIR.mkdir(exist_ok=True)
    job_file = config.RENDER_QUEUE_DIR / f"{story_path.stem}.json"
    job_file.write_text(json.dumps(job, indent=2))
    return redirect(url_for("index"))


@cli.command()
def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the Flask development server."""
    app.run(host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    cli()
