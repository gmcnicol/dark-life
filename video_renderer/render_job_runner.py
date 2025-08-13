"""Worker that polls the render jobs API and dispatches renders."""

from __future__ import annotations


import asyncio
import json
import logging
from typing import Any

import httpx
import typer

from shared.config import settings
from shared.types import RenderJob
from . import create_slideshow, voiceover, whisper_subs

logger = logging.getLogger(__name__)
app = typer.Typer(add_completion=False)


async def _heartbeat(client: httpx.AsyncClient, job_id: str, interval: float) -> None:
    """Send periodic heartbeats for ``job_id`` until cancelled."""

    try:
        while True:
            await asyncio.sleep(interval)
            await client.post(f"/api/render-jobs/{job_id}/heartbeat")
    except asyncio.CancelledError:  # pragma: no cover - cancelled when job ends
        pass
    except Exception:  # pragma: no cover - best effort heartbeat
        logger.exception("heartbeat failed for %s", job_id)


async def _process_api_job(job: dict[str, Any]) -> None:
    """Placeholder for processing jobs fetched from the API."""

    await asyncio.sleep(0)


def _process_job(job: RenderJob) -> bool:
    story_id = job.story_path.stem

    try:
        voiceover.main(
            input_dir=settings.STORIES_DIR,
            output_dir=settings.CONTENT_DIR / "audio" / "voiceovers",
        )
    except Exception:
        logger.exception("Voiceover generation failed for %s", story_id)
        return False

    try:
        whisper_subs.main(
            input_dir=settings.CONTENT_DIR / "audio" / "voiceovers",
            output_dir=settings.CONTENT_DIR / "subtitles",
        )
    except Exception:
        logger.exception("Subtitle creation failed for %s", story_id)
        return False

    try:
        create_slideshow.main(
            [
                "--story_id",
                story_id,
                "--subtitles-dir",
                str(settings.CONTENT_DIR / "subtitles"),
            ]
        )
    except Exception:
        logger.exception("Slideshow rendering failed for %s", story_id)
        return False

    settings.MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "story": story_id,
        "video": str((settings.VIDEO_OUTPUT_DIR / f"{story_id}_final.mp4").resolve()),
    }
    (settings.MANIFEST_DIR / f"{story_id}.json").write_text(json.dumps(manifest, indent=2))
    return True


async def _run_job(
    client: httpx.AsyncClient, job: dict[str, Any], sem: asyncio.Semaphore
) -> None:
    """Run a single claimed job under ``sem`` concurrency control."""

    async with sem:
        if isinstance(job, RenderJob):
            job_id = job.story_path.stem
            lease_sec = settings.LEASE_SECONDS
        else:
            job_id = str(job.get("id"))
            lease_sec = int(job.get("lease_seconds", settings.LEASE_SECONDS))
        hb_task = asyncio.create_task(_heartbeat(client, job_id, max(lease_sec / 2, 5)))
        try:
            await client.post(
                f"/api/render-jobs/{job_id}/status", json={"status": "rendering"}
            )
            if isinstance(job, RenderJob):
                success = await asyncio.to_thread(_process_job, job)
            else:
                await _process_api_job(job)
                success = True
            if success:
                await client.post(
                    f"/api/render-jobs/{job_id}/status",
                    json={"status": "rendered", "metadata": {}},
                )
            else:
                raise RuntimeError("processing failed")
        except Exception as exc:  # pragma: no cover - error path
            await client.post(
                f"/api/render-jobs/{job_id}/status",
                json={"status": "errored", "error_message": str(exc)},
            )
        finally:
            hb_task.cancel()


async def _poll_loop() -> None:
    """Continuously poll the API for queued jobs and dispatch them."""

    headers = {"Authorization": f"Bearer {settings.ADMIN_API_TOKEN}"}
    sem = asyncio.Semaphore(settings.MAX_CONCURRENT)
    async with httpx.AsyncClient(
        base_url=settings.API_BASE_URL, headers=headers, timeout=30.0
    ) as client:
        while True:
            try:
                resp = await client.get(
                    "/api/render-jobs",
                    params={"status": "queued", "limit": settings.MAX_CLAIM},
                )
                resp.raise_for_status()
                jobs = resp.json()
                queue_depth = len(jobs)
                logger.info(
                    json.dumps({"event": "poll", "queue_depth": queue_depth})
                )
                for job in jobs:
                    job_id = str(job.get("id"))
                    try:
                        claim_resp = await client.post(
                            f"/api/render-jobs/{job_id}/claim",
                            json={"lease_seconds": settings.LEASE_SECONDS},
                        )
                        claim_resp.raise_for_status()
                        logger.info(
                            json.dumps(
                                {
                                    "event": "claim",
                                    "job_id": job_id,
                                    "story_id": job.get("story_id"),
                                    "part_id": job.get("part_id"),
                                    "lease_sec": job.get(
                                        "lease_seconds", settings.LEASE_SECONDS
                                    ),
                                    "queue_depth": queue_depth,
                                }
                            )
                        )
                        asyncio.create_task(_run_job(client, job, sem))
                    except Exception:  # pragma: no cover - claim failure
                        logger.exception("claim failed for %s", job_id)
            except Exception:  # pragma: no cover - poll failure
                logger.exception("poll failed")

            await asyncio.sleep(settings.POLL_INTERVAL_MS / 1000)


@app.command()
def run() -> None:
    """Entry point for the CLI."""

    asyncio.run(_poll_loop())


if __name__ == "__main__":  # pragma: no cover
    app()

