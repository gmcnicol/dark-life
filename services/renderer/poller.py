from __future__ import annotations

"""Simple poller that processes queued ``render_part`` jobs from the database.

The worker downloads/copies the selected images, generates a placeholder
narration and subtitles, renders a vertical slideshow and stores the resulting
video to :mod:`output/videos`.
"""

import json
import re
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import requests
import typer
from sqlmodel import Session, create_engine, select

from apps.api.models import Asset, Job, Story, StoryPart
from shared.config import settings
from video_renderer import create_slideshow, whisper_subs, voiceover

app = typer.Typer(add_completion=False)


def _slugify(text: str) -> str:
    """Return a filesystem-friendly slug."""

    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower() or "story"


def _segment_text(text: str) -> list[SimpleNamespace]:
    """Very small helper that creates fake subtitle segments from ``text``."""

    sentences = [s.strip() for s in re.split(r"(?<=[.!?]) +", text) if s.strip()]
    if not sentences:
        sentences = [text]
    start = 0.0
    segments: list[SimpleNamespace] = []
    for sent in sentences:
        duration = max(1.0, len(sent.split()) * 0.5)
        segments.append(SimpleNamespace(start=start, end=start + duration, text=sent))
        start += duration
    return segments


def process_once(session: Session) -> bool:
    """Process a single queued ``render_part`` job."""

    job = (
        session.exec(
            select(Job)
            .where(Job.status == "queued", Job.kind == "render_part")
            .order_by(Job.created_at)
            .limit(1)
        ).first()
    )
    if job is None:
        return False

    job.status = "running"
    session.add(job)
    session.commit()
    session.refresh(job)

    payload = job.payload or {}
    story_id = payload.get("story_id")
    part_index = payload.get("part_index")
    asset_ids = payload.get("asset_ids") or []
    if story_id is None or part_index is None or not asset_ids:
        job.status = "failed"
        session.add(job)
        session.commit()
        return True

    story = session.get(Story, story_id)
    part = (
        session.exec(
            select(StoryPart)
            .where(StoryPart.story_id == story_id, StoryPart.index == part_index)
        ).first()
    )
    if not story or not part:
        job.status = "failed"
        session.add(job)
        session.commit()
        return True

    slug = _slugify(story.title)
    part_slug = f"{slug}_p{int(part_index):02d}"

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            visuals_dir = tmp / "visuals"
            voice_dir = tmp / "voice"
            subs_dir = tmp / "subs"
            for d in (visuals_dir, voice_dir, subs_dir):
                d.mkdir(parents=True, exist_ok=True)

            assets = session.exec(select(Asset).where(Asset.id.in_(asset_ids))).all()
            for idx, asset in enumerate(assets):
                dest = visuals_dir / f"{part_slug}_{idx}.jpg"
                resp = requests.get(asset.remote_url, timeout=30)
                resp.raise_for_status()
                dest.write_bytes(resp.content)

            text = part.body_md or ""
            voice_path = voice_dir / f"{part_slug}.mp3"
            if not voiceover._synth_with_pyttsx3(voiceover.engine, text, voice_path):
                voiceover._placeholder_audio(text, voice_path)

            segments = _segment_text(text)
            whisper_subs._write_srt(segments, subs_dir / f"{part_slug}.srt")

            settings.VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            result = create_slideshow.main(
                [
                    "--story_id",
                    part_slug,
                    "--visuals-dir",
                    str(visuals_dir),
                    "--voice-dir",
                    str(voice_dir),
                    "--subtitles-dir",
                    str(subs_dir),
                    "--output-dir",
                    str(settings.VIDEO_OUTPUT_DIR),
                ]
            )
            if result != 0:
                raise RuntimeError("slideshow failed")

            produced = settings.VIDEO_OUTPUT_DIR / f"{part_slug}_final.mp4"
            final_path = settings.VIDEO_OUTPUT_DIR / f"{part_slug}.mp4"
            if produced.exists():
                produced.replace(final_path)
            else:
                raise RuntimeError("output video missing")

        job.result = {"video": final_path.name}
        job.status = "success"
    except Exception as exc:  # pragma: no cover - error path
        job.result = {"error": str(exc)}
        job.status = "failed"

    session.add(job)
    session.commit()

    # Log payload for debugging
    print(json.dumps(payload))
    return True


@app.command()
def run(interval: float = 1.0) -> None:
    """Continuously poll for queued render_part jobs."""
    engine = create_engine(settings.DATABASE_URL, echo=False)
    while True:
        with Session(engine) as session:
            processed = process_once(session)
        if not processed:
            time.sleep(interval)


if __name__ == "__main__":  # pragma: no cover
    app()
