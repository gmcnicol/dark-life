"""Cron-style uploader that scans output manifests and uploads videos."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from shared.config import settings
from . import upload_to_instagram, upload_to_tiktok, upload_youtube

app = typer.Typer(add_completion=False)


@app.command()
def run(insta_user: str = "", insta_pass: str = "") -> None:
    """Upload all videos described in manifest files."""
    for manifest in sorted(settings.MANIFEST_DIR.glob("*.json")):
        data = json.loads(manifest.read_text())
        video = Path(data["video"])
        caption = data.get("title", "")
        if insta_user and insta_pass:
            upload_to_instagram.upload(video, caption, insta_user, insta_pass)
        else:
            print("Instagram credentials missing; skipping upload")

        yt_secret = settings.YOUTUBE_CLIENT_SECRETS_FILE
        yt_token = settings.YOUTUBE_TOKEN_FILE
        if (
            (yt_secret and yt_secret.exists())
            or (yt_token and yt_token.exists())
        ):
            upload_youtube.upload(video, caption, yt_secret, yt_token)
        else:
            print("YouTube credentials missing; skipping upload")

        upload_to_tiktok.upload(video, caption)
        manifest.unlink()


if __name__ == "__main__":  # pragma: no cover
    app()
