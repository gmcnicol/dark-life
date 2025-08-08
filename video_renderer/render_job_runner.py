"""Simple worker that polls the render queue and renders videos."""

from __future__ import annotations

import json
from pathlib import Path

import logging
import typer

from . import create_slideshow, voiceover, whisper_subs
from shared.config import settings
from shared.types import RenderJob

logger = logging.getLogger(__name__)
app = typer.Typer(add_completion=False)


def _load_job(path: Path) -> RenderJob:
    data = json.loads(path.read_text())
    return RenderJob(
        story_path=Path(data["story_path"]),
        image_paths=[Path(p) for p in data.get("image_paths", [])],
    )


def _process_job(job: RenderJob) -> bool:
    story_id = job.story_path.stem

    # Generate voiceover
    try:
        voiceover.main(
            input_dir=settings.STORIES_DIR,
            output_dir=settings.CONTENT_DIR / "audio" / "voiceovers",
        )
    except Exception:
        logger.exception("Voiceover generation failed for %s", story_id)
        return False

    # Create subtitles
    try:
        whisper_subs.main(
            input_dir=settings.CONTENT_DIR / "audio" / "voiceovers",
            stories_dir=settings.STORIES_DIR,
        )
    except Exception:
        logger.exception("Subtitle creation failed for %s", story_id)
        return False

    # Create video slideshow
    try:
        create_slideshow.main(["--story_id", story_id])
    except Exception:
        logger.exception("Slideshow rendering failed for %s", story_id)
        return False

    # Write manifest
    settings.MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "story": story_id,
        "video": str((settings.VIDEO_OUTPUT_DIR / f"{story_id}_final.mp4").resolve()),
    }
    (settings.MANIFEST_DIR / f"{story_id}.json").write_text(json.dumps(manifest, indent=2))
    return True


@app.command()
def run() -> None:
    """Process all jobs in the render queue."""
    settings.RENDER_QUEUE_DIR.mkdir(exist_ok=True)
    for job_file in sorted(settings.RENDER_QUEUE_DIR.glob("*.json")):
        try:
            job = _load_job(job_file)
        except Exception:
            logger.exception("Failed to load job %s", job_file)
            continue

        try:
            success = _process_job(job)
        except Exception:
            logger.exception("Unexpected error processing job %s", job_file)
            continue

        if success:
            job_file.unlink()


if __name__ == "__main__":  # pragma: no cover
    app()
