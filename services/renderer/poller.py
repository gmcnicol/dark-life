from __future__ import annotations

"""Poller that renders stories by fetching work from the API."""

import json
import re
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import requests
import typer

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


def process_once() -> bool:
    """Fetch the next series to render from the API and process it."""
    base = settings.API_BASE_URL.rstrip("/")
    headers = {}
    if settings.API_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {settings.API_AUTH_TOKEN}"
    resp = requests.get(f"{base}/render/next-series", timeout=30, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    story = data.get("story")
    if not story:
        return False
    assets = data.get("assets", [])
    parts = data.get("parts", [])
    slug = _slugify(story.get("title", "story"))
    asset_urls = [a.get("remote_url", "") for a in assets]
    processed_any = False
    for part in parts:
        job_id = part.get("job_id")
        part_index = part.get("index")
        text = part.get("body_md", "")
        if job_id is None or part_index is None:
            continue
        part_slug = f"{slug}_p{int(part_index):02d}"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                visuals_dir = tmp / "visuals"
                voice_dir = tmp / "voice"
                subs_dir = tmp / "subs"
                for d in (visuals_dir, voice_dir, subs_dir):
                    d.mkdir(parents=True, exist_ok=True)
                for idx, url in enumerate(asset_urls):
                    if not url:
                        continue
                    dest = visuals_dir / f"{part_slug}_{idx}.jpg"
                    r = requests.get(url, timeout=30)
                    r.raise_for_status()
                    dest.write_bytes(r.content)
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
            requests.patch(
                f"{base}/jobs/{job_id}",
                json={"status": "success", "result": {"video": final_path.name}},
                timeout=30,
                headers=headers,
            )
        except Exception as exc:  # pragma: no cover - error path
            requests.patch(
                f"{base}/jobs/{job_id}",
                json={"status": "failed", "result": {"error": str(exc)}} ,
                timeout=30,
                headers=headers,
            )
        print(json.dumps({"job_id": job_id, "part_index": part_index}))
        processed_any = True
    return processed_any


@app.command()
def run(interval: float = 1.0) -> None:
    """Continuously poll for queued render_part jobs via the API."""
    while True:
        processed = process_once()
        if not processed:
            time.sleep(interval)


if __name__ == "__main__":  # pragma: no cover
    app()
