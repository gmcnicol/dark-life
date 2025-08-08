"""Cron-style uploader that scans output manifests and uploads videos."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from shared.config import settings
from . import upload_to_instagram, upload_to_tiktok

app = typer.Typer(add_completion=False)


@app.command()
def run(insta_user: str = "", insta_pass: str = "") -> None:
    """Upload all videos described in manifest files."""
    for manifest in sorted(settings.MANIFEST_DIR.glob("*.json")):
        data = json.loads(manifest.read_text())
        video = Path(data["video"])
        caption = data.get("title", "")
        upload_to_instagram.upload(video, caption, insta_user, insta_pass)
        upload_to_tiktok.upload(video, caption)
        manifest.unlink()


if __name__ == "__main__":  # pragma: no cover
    app()
