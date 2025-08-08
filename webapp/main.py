"""Simple web UI for managing stories and rendering jobs."""

from __future__ import annotations

import json
import os
from typing import List

from flask import Flask, redirect, render_template, request, url_for
import typer

from shared.config import settings
from shared.reddit import fetch_top_stories

app = Flask(__name__, template_folder="templates", static_folder="static")
cli = typer.Typer()


@cli.callback()
def main() -> None:
    """CLI entry point for the web application."""
    pass


@app.route("/")
def index():
    stories = sorted(settings.STORIES_DIR.glob("*.md"))
    return render_template("index.html", stories=[s.name for s in stories])


@app.post("/fetch")
def fetch():
    fetch_top_stories()
    return redirect(url_for("index"))


@app.post("/queue")
def queue_story():
    story_name = os.path.basename(request.form.get("story", ""))
    images = [os.path.basename(i) for i in request.form.get("images", "").split()]

    story_dir = settings.STORIES_DIR.resolve()
    story_path = (story_dir / story_name).resolve()
    if not story_name or not story_path.is_file() or not story_path.is_relative_to(story_dir):
        return ("Invalid story path", 400)

    visuals_dir = settings.VISUALS_DIR.resolve()
    image_paths: List[str] = []
    for img in images:
        if not img:
            continue
        img_path = (visuals_dir / img).resolve()
        if not img_path.is_file() or not img_path.is_relative_to(visuals_dir):
            return ("Invalid image path", 400)
        image_paths.append(str(img_path))

    job = {"story_path": str(story_path), "image_paths": image_paths}
    settings.RENDER_QUEUE_DIR.mkdir(exist_ok=True)
    job_file = settings.RENDER_QUEUE_DIR / f"{story_path.stem}.json"
    job_file.write_text(json.dumps(job, indent=2))
    return redirect(url_for("index"))


@cli.command()
def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the Flask development server."""
    app.run(host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    cli()
