from __future__ import annotations

"""Upload the next rendered part to YouTube Shorts."""

from pathlib import Path
import json
import subprocess
from typing import Optional

import typer
from sqlmodel import Session, create_engine

from apps.api.models import Upload
from apps.api.uploads import next_part_ready_for_upload
from shared.config import settings
from video_uploader import upload_youtube

app = typer.Typer(add_completion=False)


def _video_ok(video: Path) -> bool:
    """Return True if ``video`` is vertical and <= 60 seconds."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,duration",
                "-of",
                "json",
                str(video),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        info = json.loads(result.stdout)
        stream = info.get("streams", [{}])[0]
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        duration = float(stream.get("duration", 0.0))
    except Exception as exc:  # pragma: no cover - ffprobe missing
        print(f"ffprobe failed: {exc}")
        return False

    if height <= width:
        print("Video is not vertical; skipping upload")
        return False
    if duration > 60:
        print(f"Video is {duration:.2f}s; exceeds 60s limit")
        return False
    return True


@app.command()
def run(dry_run: bool = typer.Option(False, "--dry-run", is_flag=True)) -> None:
    """Upload the earliest rendered part that hasn't been uploaded."""
    engine = create_engine(settings.DATABASE_URL, echo=False)
    with Session(engine) as session:
        result = next_part_ready_for_upload(session, platform="youtube")
        if not result:
            print("No parts ready for upload")
            return
        job, story = result
        payload = job.payload or {}
        part_index: Optional[int] = payload.get("part_index")
        if part_index is None:
            print("Job missing part_index; aborting")
            return
        video_name = (job.result or {}).get("video")
        if not video_name:
            print("Job missing video filename; aborting")
            return
        video_path = settings.VIDEO_OUTPUT_DIR / video_name
        if not video_path.exists():
            print(f"Video file not found: {video_path}")
            return
        if not _video_ok(video_path):
            return
        title = f"{story.title} — Part {part_index}"
        if dry_run:
            print(f"[DRY RUN] Would upload {video_path} as '{title}'")
            return
        video_id = upload_youtube.upload(
            video_path,
            title,
            settings.YOUTUBE_CLIENT_SECRETS_FILE,
            settings.YOUTUBE_TOKEN_FILE,
        )
        if not video_id:
            print("Upload failed; no record inserted")
            return
        session.add(
            Upload(
                story_id=story.id,
                part_index=part_index,
                platform="youtube",
                platform_video_id=video_id,
            )
        )
        session.commit()
        print(f"Uploaded https://youtu.be/{video_id}")


if __name__ == "__main__":  # pragma: no cover
    app()
