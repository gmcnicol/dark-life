"""Worker that polls the render jobs API and dispatches renders."""

from __future__ import annotations


import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import typer

from shared.config import settings
from shared.logging import log_error, log_info
from shared.types import RenderJob
from . import create_slideshow, voiceover, whisper_subs

app = typer.Typer(add_completion=False)


class LeaseExpired(RuntimeError):
    """Raised when a job lease expires before completion."""


async def _heartbeat(
    client: httpx.AsyncClient,
    job_id: str,
    story_id: str | None,
    part_id: str | None,
    interval: float,
    lease_deadline: list[float],
) -> None:
    """Send periodic heartbeats for ``job_id`` until cancelled.

    ``lease_deadline`` is a single-item list containing the epoch time when the
    lease currently expires. Each successful heartbeat updates this value.
    """

    start = time.monotonic()
    try:
        while True:
            await asyncio.sleep(interval)
            resp = await client.post(f"/api/render-jobs/{job_id}/heartbeat")
            try:
                data = resp.json()
                expires = data.get("lease_expires_at")
                if expires:
                    lease_deadline[0] = datetime.fromisoformat(
                        expires.replace("Z", "+00:00")
                    ).timestamp()
            except Exception:
                pass
            elapsed = int(time.monotonic() - start)
            log_info(
                "rendering",
                job_id=job_id,
                story_id=story_id,
                part_id=part_id,
                elapsed_sec=elapsed,
            )
    except asyncio.CancelledError:  # pragma: no cover - cancelled when job ends
        pass
    except Exception as exc:  # pragma: no cover - best effort heartbeat
        log_error(
            "error",
            job_id=job_id,
            story_id=story_id,
            part_id=part_id,
            error_class=exc.__class__.__name__,
            error_message=str(exc),
        )


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
    except Exception as exc:
        log_error(
            "error",
            job_id=story_id,
            story_id=story_id,
            error_class=exc.__class__.__name__,
            error_message=str(exc),
        )
        return False

    try:
        whisper_subs.main(
            input_dir=settings.CONTENT_DIR / "audio" / "voiceovers",
            output_dir=settings.CONTENT_DIR / "subtitles",
        )
    except Exception as exc:
        log_error(
            "error",
            job_id=story_id,
            story_id=story_id,
            error_class=exc.__class__.__name__,
            error_message=str(exc),
        )
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
    except Exception as exc:
        log_error(
            "error",
            job_id=story_id,
            story_id=story_id,
            error_class=exc.__class__.__name__,
            error_message=str(exc),
        )
        return False

    settings.MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "story": story_id,
        "video": str((settings.VIDEO_OUTPUT_DIR / f"{story_id}_final.mp4").resolve()),
    }
    (settings.MANIFEST_DIR / f"{story_id}.json").write_text(json.dumps(manifest, indent=2))
    return True


async def _run_job(
    client: httpx.AsyncClient,
    job: dict[str, Any],
    sem: asyncio.Semaphore,
    lease_expires_at: str | None = None,
) -> None:
    """Run a single claimed job under ``sem`` concurrency control."""

    async with sem:
        if isinstance(job, RenderJob):
            job_id = story_id = job.story_path.stem
            part_id = None
            lease_sec = settings.LEASE_SECONDS
        else:
            job_id = str(job.get("id"))
            story_id = job.get("story_id")
            part_id = job.get("part_id")
            lease_sec = int(job.get("lease_seconds", settings.LEASE_SECONDS))

        if lease_expires_at:
            try:
                lease_deadline = [
                    datetime.fromisoformat(lease_expires_at.replace("Z", "+00:00")).timestamp()
                ]
            except Exception:
                lease_deadline = [time.time() + lease_sec]
        else:
            lease_deadline = [time.time() + lease_sec]

        # Heartbeat every 5-10 seconds to maintain lease and report progress
        interval = max(lease_sec / 2, 5)
        interval = min(interval, 10)
        hb_task = asyncio.create_task(
            _heartbeat(client, job_id, story_id, part_id, interval, lease_deadline)
        )
        job_deadline = time.time() + settings.JOB_TIMEOUT_SEC
        job_task = (
            asyncio.to_thread(_process_job, job)
            if isinstance(job, RenderJob)
            else _process_api_job(job)
        )
        job_task = asyncio.create_task(job_task)
        try:
            await client.post(
                f"/api/render-jobs/{job_id}/status", json={"status": "rendering"}
            )
            while True:
                now = time.time()
                remaining = min(lease_deadline[0], job_deadline) - now
                if remaining <= 0:
                    raise asyncio.TimeoutError
                try:
                    await asyncio.wait_for(job_task, timeout=remaining)
                    break
                except asyncio.TimeoutError:
                    now = time.time()
                    if now >= job_deadline:
                        raise asyncio.TimeoutError
                    if now >= lease_deadline[0]:
                        raise LeaseExpired()
                    continue

            if isinstance(job, RenderJob):
                success = job_task.result()
                if not success:
                    raise RuntimeError("processing failed")
            await client.post(
                f"/api/render-jobs/{job_id}/status",
                json={"status": "rendered", "metadata": {}},
            )
        except asyncio.TimeoutError:
            await client.post(
                f"/api/render-jobs/{job_id}/status",
                json={
                    "status": "errored",
                    "error_class": "TimeoutError",
                    "error_message": "job timed out",
                    "timeout": True,
                },
            )
            log_error(
                "error",
                job_id=job_id,
                story_id=story_id,
                part_id=part_id,
                error_class="TimeoutError",
                error_message="job timed out",
            )
        except LeaseExpired:
            await client.post(
                f"/api/render-jobs/{job_id}/status",
                json={
                    "status": "errored",
                    "error_class": "LeaseExpired",
                    "error_message": "lease expired",
                },
            )
            log_error(
                "error",
                job_id=job_id,
                story_id=story_id,
                part_id=part_id,
                error_class="LeaseExpired",
                error_message="lease expired",
            )
        except create_slideshow.RenderError:
            pass
        except Exception as exc:  # pragma: no cover - error path
            await client.post(
                f"/api/render-jobs/{job_id}/status",
                json={
                    "status": "errored",
                    "error_class": exc.__class__.__name__,
                    "error_message": str(exc),
                },
            )
            log_error(
                "error",
                job_id=job_id,
                story_id=story_id,
                part_id=part_id,
                error_class=exc.__class__.__name__,
                error_message=str(exc),
            )
        finally:
            hb_task.cancel()


async def _poll_loop() -> None:
    """Continuously poll the API for queued jobs and dispatch them."""

    headers = {"Authorization": f"Bearer {settings.API_AUTH_TOKEN}"}
    sem = asyncio.Semaphore(settings.MAX_CONCURRENT)
    log_info(
        "start",
        poll_interval_ms=settings.POLL_INTERVAL_MS,
        max_concurrent=settings.MAX_CONCURRENT,
        lease_seconds=settings.LEASE_SECONDS,
        api_base=settings.API_BASE_URL,
        content_dir=str(settings.CONTENT_DIR),
        music_dir=str(settings.MUSIC_DIR),
        output_dir=str(settings.OUTPUT_DIR),
    )
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
                log_info("poll", queue_depth=queue_depth)
                for job in jobs:
                    job_id = str(job.get("id"))
                    try:
                        claim_resp = await client.post(
                            f"/api/render-jobs/{job_id}/claim",
                            json={"lease_seconds": settings.LEASE_SECONDS},
                        )
                        claim_resp.raise_for_status()
                        claim_data = claim_resp.json()
                        log_info(
                            "claim",
                            job_id=job_id,
                            story_id=job.get("story_id"),
                            part_id=job.get("part_id"),
                            lease_sec=job.get("lease_seconds", settings.LEASE_SECONDS),
                            queue_depth=queue_depth,
                        )
                        asyncio.create_task(
                            _run_job(client, job, sem, claim_data.get("lease_expires_at"))
                        )
                    except Exception as exc:  # pragma: no cover - claim failure
                        log_error(
                            "error",
                            job_id=job_id,
                            story_id=job.get("story_id"),
                            part_id=job.get("part_id"),
                            error_class=exc.__class__.__name__,
                            error_message=str(exc),
                        )
            except Exception as exc:  # pragma: no cover - poll failure
                log_error(
                    "error",
                    error_class=exc.__class__.__name__,
                    error_message=str(exc),
                )

            await asyncio.sleep(settings.POLL_INTERVAL_MS / 1000)


@app.command()
def run(
    api_base_url: str = typer.Option(
        settings.API_BASE_URL, "--api-base-url", help="API base URL"
    ),
    api_auth_token: str = typer.Option(
        settings.API_AUTH_TOKEN, "--api-auth-token", help="API bearer token"
    ),
    poll_interval_ms: int = typer.Option(
        settings.POLL_INTERVAL_MS, "--poll-interval-ms", help="Poll interval in ms"
    ),
    max_concurrent: int = typer.Option(
        settings.MAX_CONCURRENT, "--max-concurrent", help="Max concurrent jobs"
    ),
    lease_seconds: int = typer.Option(
        settings.LEASE_SECONDS, "--lease-seconds", help="Job lease in seconds"
    ),
    job_timeout_sec: int = typer.Option(
        settings.JOB_TIMEOUT_SEC, "--job-timeout-sec", help="Max seconds per job"
    ),
    content_dir: Path = typer.Option(
        settings.CONTENT_DIR, "--content-dir", help="Content directory"
    ),
    music_dir: Path = typer.Option(
        settings.MUSIC_DIR, "--music-dir", help="Music directory"
    ),
    output_dir: Path = typer.Option(
        settings.OUTPUT_DIR, "--output-dir", help="Output directory"
    ),
    tmp_dir: Path = typer.Option(
        settings.TMP_DIR, "--tmp-dir", help="Temporary working directory"
    ),
) -> None:
    """Entry point for the CLI."""

    settings.API_BASE_URL = api_base_url
    settings.API_AUTH_TOKEN = api_auth_token
    settings.POLL_INTERVAL_MS = poll_interval_ms
    settings.MAX_CONCURRENT = max_concurrent
    settings.LEASE_SECONDS = lease_seconds
    settings.JOB_TIMEOUT_SEC = job_timeout_sec
    settings.CONTENT_DIR = content_dir
    settings.MUSIC_DIR = music_dir
    settings.OUTPUT_DIR = output_dir
    settings.TMP_DIR = tmp_dir

    asyncio.run(_poll_loop())


if __name__ == "__main__":  # pragma: no cover
    app()

