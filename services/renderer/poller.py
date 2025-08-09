from __future__ import annotations

"""Simple poller that processes queued render jobs from the jobs table."""

import json
import sqlite3
import time
from pathlib import Path

import requests
import typer

from shared.config import settings
from shared.types import RenderJob
from video_renderer import render_job_runner

app = typer.Typer(add_completion=False)


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _db_path() -> Path:
    """Return path to the jobs database."""
    return settings.BASE_DIR / "jobs.db"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)
    conn.commit()


def process_once(conn: sqlite3.Connection) -> bool:
    """Process a single queued render job.

    Returns True if a job was processed.
    """
    cur = conn.execute(
        "SELECT id, payload FROM jobs WHERE status = 'queued' AND kind = 'render' ORDER BY created_at LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        return False

    job_id, payload_json = row
    conn.execute(
        "UPDATE jobs SET status = 'running', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (job_id,),
    )
    conn.commit()

    payload = json.loads(payload_json)
    # Display raw payload for logging/debugging purposes
    print(payload_json)
    story_id = payload.get("story_id")
    image_urls = payload.get("image_urls")
    if image_urls is None:
        # Legacy payload format; mark success without processing
        conn.execute(
            "UPDATE jobs SET status = 'success', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (job_id,),
        )
        conn.commit()
        return True

    voiceover_url = payload.get("voiceover_url")

    image_paths: list[Path] = []
    settings.VISUALS_DIR.mkdir(parents=True, exist_ok=True)
    for idx, url in enumerate(image_urls):
        dest = settings.VISUALS_DIR / f"{story_id}_{idx}.jpg"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            image_paths.append(dest)
        except Exception:
            conn.execute(
                "UPDATE jobs SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (job_id,),
            )
            conn.commit()
            return True

    if voiceover_url:
        voice_dir = settings.CONTENT_DIR / "audio" / "voiceovers"
        voice_dir.mkdir(parents=True, exist_ok=True)
        voice_path = voice_dir / f"{story_id}.mp3"
        try:
            resp = requests.get(voiceover_url, timeout=30)
            resp.raise_for_status()
            voice_path.write_bytes(resp.content)
        except Exception:
            conn.execute(
                "UPDATE jobs SET status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (job_id,),
            )
            conn.commit()
            return True

    job = RenderJob(
        story_path=settings.STORIES_DIR / f"{story_id}.md",
        image_paths=image_paths,
    )

    try:
        success = render_job_runner._process_job(job)
    except Exception:
        success = False

    conn.execute(
        "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        ("success" if success else "failed", job_id),
    )
    conn.commit()
    return True


@app.command()
def run(interval: float = 1.0) -> None:
    """Continuously poll for queued render jobs."""
    db_path = _db_path()
    conn = sqlite3.connect(db_path)
    try:
        _ensure_schema(conn)
        while True:
            processed = process_once(conn)
            if not processed:
                time.sleep(interval)
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover
    app()
