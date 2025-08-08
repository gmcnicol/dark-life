"""Simple worker that polls the render queue and renders videos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from . import create_slideshow, voiceover, whisper_subs
from shared.config import settings
from shared.types import RenderJob

app = typer.Typer(add_completion=False)


def _load_job(path: Path) -> RenderJob:
    data = json.loads(path.read_text())
    return RenderJob(
        story_path=Path(data["story_path"]),
        image_paths=[Path(p) for p in data.get("image_paths", [])],
    )


def _process_job(job: RenderJob) -> None:
    story_id = job.story_path.stem
    # Generate voiceover and subtitles
    voiceover.main(
        input_dir=settings.STORIES_DIR,
        output_dir=settings.CONTENT_DIR / "audio" / "voiceovers",
    )
    whisper_subs.main(
        input_dir=settings.CONTENT_DIR / "audio" / "voiceovers",
        stories_dir=settings.STORIES_DIR,
    )
    # Create video slideshow
    create_slideshow.main(["--story_id", story_id])
    # Write manifest
    settings.MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "story": story_id,
        "video": str((settings.VIDEO_OUTPUT_DIR / f"{story_id}_final.mp4").resolve()),
    }
    (settings.MANIFEST_DIR / f"{story_id}.json").write_text(json.dumps(manifest, indent=2))


@app.command()
def run() -> None:
    """Process all jobs in the render queue."""
    settings.RENDER_QUEUE_DIR.mkdir(exist_ok=True)
    for job_file in sorted(settings.RENDER_QUEUE_DIR.glob("*.json")):
        job = _load_job(job_file)
        _process_job(job)
        job_file.unlink()


if __name__ == "__main__":  # pragma: no cover
    app()
