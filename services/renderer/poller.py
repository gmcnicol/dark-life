"""Renderer job poller interacting with the Dark Life API."""

from __future__ import annotations

import shutil
import threading
import time
import uuid
import random
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from shared.config import settings
from shared.logging import log_error, log_info
from shared.workflow import JobStatus

from .api_client import RenderApiClient, auth_headers
from .executor import CommandExecutionError, CommandTimeoutError
from .pipeline import render_job as render_pipeline_job


DISK_MIN_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
HEARTBEAT_FILE = Path(settings.TMP_DIR) / "worker_heartbeat"


def backoff_schedule(
    base_ms: int, factor: float = 1.0, rand: Callable[[], float] = random.random
) -> Iterable[float]:
    """Yield successive delays in seconds using jitter and optional backoff."""
    delay_ms = base_ms
    while True:
        jitter_ms = rand() * delay_ms
        yield (delay_ms + jitter_ms) / 1000.0
        delay_ms = max(base_ms, int(delay_ms * factor))


def _check_disk(job_id: int | str, cid: str) -> bool:
    tmp = Path(settings.TMP_DIR)
    tmp.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(tmp)
    if usage.free < DISK_MIN_BYTES:
        log_error("disk_low", cid=cid, job_id=job_id, free_bytes=usage.free)
        return False
    return True


def _validate_runtime() -> None:
    missing = [binary for binary in ("ffmpeg", "ffprobe") if shutil.which(binary) is None]
    if missing:
        raise RuntimeError(f"Missing required binaries: {', '.join(missing)}")
    if not settings.API_BASE_URL:
        raise RuntimeError("API_BASE_URL is required")
    if not settings.ELEVENLABS_VOICE_ID:
        log_info("config_warning", field="ELEVENLABS_VOICE_ID", message="TTS voice is unset")
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.TMP_DIR).mkdir(parents=True, exist_ok=True)


def poll_jobs(session: requests.sessions.Session | None = None) -> list[dict]:
    client = RenderApiClient(session or requests)
    jobs = client.list_jobs(status=JobStatus.QUEUED.value, limit=settings.MAX_CLAIM)
    log_info("poll", cid="poll", count=len(jobs))
    return jobs


def _heartbeat_loop(
    job_id: int,
    cid: str,
    stop: threading.Event,
    lost: list[bool],
    session: requests.sessions.Session | None = None,
) -> None:
    sess = session or requests
    base = settings.API_BASE_URL.rstrip("/")
    while not stop.wait(settings.HEARTBEAT_INTERVAL_SEC):
        try:
            resp = sess.post(
                f"{base}/render-jobs/{job_id}/heartbeat",
                timeout=30,
                headers=auth_headers(),
            )
            if resp.status_code in (409, 410):
                lost[0] = True
                stop.set()
                log_error("heartbeat", cid=cid, job_id=job_id, status=resp.status_code)
                return
            resp.raise_for_status()
            log_info("heartbeat", cid=cid, job_id=job_id)
        except Exception as exc:
            log_error("heartbeat", cid=cid, job_id=job_id, error=str(exc))


def render_job(job: dict, session: requests.sessions.Session | None = None) -> dict[str, object]:
    client = RenderApiClient(session or requests)
    context = client.get_context(int(job["id"]))
    log_info(
        "context",
        job_id=job["id"],
        story_id=context["story"]["id"],
        part_id=(context.get("story_part") or {}).get("id"),
        asset_id=(context.get("selected_asset") or {}).get("key"),
    )
    return render_pipeline_job(context, session=session)


def process_job(job: dict, session: requests.sessions.Session | None = None) -> None:
    sess = session or requests
    client = RenderApiClient(sess)
    base = settings.API_BASE_URL.rstrip("/")
    job_id = int(job["id"])
    cid = job.get("correlation_id") or str(uuid.uuid4())
    job_dir = Path(settings.TMP_DIR) / str(job_id)
    if not _check_disk(job_id, cid):
        return

    try:
        claim_response = sess.post(
            f"{base}/render-jobs/{job_id}/claim",
            json={"lease_seconds": settings.LEASE_SECONDS},
            timeout=30,
            headers=auth_headers(),
        )
        if claim_response.status_code in (409, 410):
            log_error("claim", cid=cid, job_id=job_id, status=claim_response.status_code)
            return
        claim_response.raise_for_status()
        log_info("claim", cid=cid, job_id=job_id)
        client.set_status(job_id, {"status": JobStatus.RENDERING.value})

        job_dir.mkdir(parents=True, exist_ok=True)
        stop = threading.Event()
        lost = [False]
        hb_thread = threading.Thread(
            target=_heartbeat_loop,
            args=(job_id, cid, stop, lost, session),
            daemon=True,
        )
        hb_thread.start()

        result_holder: dict[str, object] = {}
        error_holder: list[Exception] = []

        def _run_render() -> None:
            try:
                result_holder.update(render_job(job, session=session))
            except Exception as exc:
                error_holder.append(exc)

        worker = threading.Thread(target=_run_render, daemon=True)
        worker.start()
        worker.join(timeout=settings.JOB_TIMEOUT_SEC)
        stop.set()
        hb_thread.join()

        if worker.is_alive():
            log_error("error", cid=cid, job_id=job_id, error="timeout")
            client.set_status(job_id, {"status": JobStatus.ERRORED.value, "error_message": "timeout"})
            return
        if lost[0]:
            log_error("error", cid=cid, job_id=job_id, error="lease_lost")
            client.set_status(job_id, {"status": JobStatus.ERRORED.value, "error_message": "lease_lost"})
            return
        if error_holder:
            exc = error_holder[0]
            payload = {
                "status": JobStatus.ERRORED.value,
                "error_class": exc.__class__.__name__,
                "error_message": str(exc),
            }
            if isinstance(exc, CommandExecutionError):
                payload["stderr_snippet"] = exc.stderr
            elif isinstance(exc, CommandTimeoutError):
                payload["stderr_snippet"] = f"timeout:{exc.timeout_sec:.1f}s"
            log_error("error", cid=cid, job_id=job_id, error=str(exc))
            client.set_status(job_id, payload)
            return

        client.set_status(job_id, {"status": JobStatus.RENDERED.value, **result_holder})
        log_info("done", cid=cid, job_id=job_id)
    except Exception as exc:
        log_error("error", cid=cid, job_id=job_id, error=str(exc))
        try:
            client.set_status(
                job_id,
                {
                    "status": JobStatus.ERRORED.value,
                    "error_class": exc.__class__.__name__,
                    "error_message": str(exc),
                },
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def run() -> None:  # pragma: no cover - continuous loop
    _validate_runtime()
    log_info("start", cid="poller")
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_FILE.touch()
    backoff = backoff_schedule(settings.POLL_INTERVAL_MS, factor=1.0)
    with ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT) as pool:
        running: dict[int, object] = {}
        while True:
            HEARTBEAT_FILE.touch()
            try:
                jobs = poll_jobs()
            except Exception as exc:
                log_error("poll", error=str(exc))
                time.sleep(next(backoff))
                continue
            for job in jobs:
                job_id = int(job["id"])
                if job_id in running or len(running) >= settings.MAX_CONCURRENT:
                    continue
                future = pool.submit(process_job, job)
                running[job_id] = future
                future.add_done_callback(lambda _f, jid=job_id: running.pop(jid, None))
            time.sleep(next(backoff))


__all__ = ["backoff_schedule", "poll_jobs", "process_job", "render_job", "run"]


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    run()
