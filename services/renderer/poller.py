"""Renderer job poller interacting with the Dark Life API."""

from __future__ import annotations

import threading
import time
import uuid
import random
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

import requests

from shared.config import settings
from shared.logging import log_error, log_info


HEARTBEAT_INTERVAL = 10  # seconds


def backoff_schedule(
    base_ms: int, factor: float = 1.0, rand: Callable[[], float] = random.random
) -> Iterable[float]:
    """Yield successive delays in seconds using jitter and optional backoff."""
    delay_ms = base_ms
    while True:
        jitter_ms = rand() * delay_ms
        yield (delay_ms + jitter_ms) / 1000.0
        delay_ms = int(delay_ms * factor)


def _headers() -> dict[str, str]:
    """Authorization headers for API requests."""
    if settings.API_AUTH_TOKEN:
        return {"Authorization": f"Bearer {settings.API_AUTH_TOKEN}"}
    return {}


def poll_jobs(session: requests.sessions.Session | None = None) -> list[dict]:
    """Fetch queued render jobs from the API."""
    sess = session or requests
    base = settings.API_BASE_URL.rstrip("/")
    resp = sess.get(
        f"{base}/api/render-jobs",
        params={"limit": settings.MAX_CLAIM},
        timeout=30,
        headers=_headers(),
    )
    resp.raise_for_status()
    jobs = resp.json() or []
    log_info("poll", cid="poll", count=len(jobs))
    return jobs


def render_job(job: dict) -> None:
    """Placeholder for the actual rendering implementation."""
    time.sleep(0.1)


def _heartbeat_loop(
    job_id: int,
    cid: str,
    stop: threading.Event,
    lost: list[bool],
    session: requests.sessions.Session | None = None,
) -> None:
    """Send heartbeats until ``stop`` is set; mark ``lost`` on lease loss."""
    sess = session or requests
    base = settings.API_BASE_URL.rstrip("/")
    while not stop.wait(HEARTBEAT_INTERVAL):
        try:
            resp = sess.post(
                f"{base}/api/render-jobs/{job_id}/heartbeat",
                timeout=30,
                headers=_headers(),
            )
            if resp.status_code in (409, 410):
                lost[0] = True
                stop.set()
                log_error("heartbeat", cid=cid, job_id=job_id, status=resp.status_code)
                return
            resp.raise_for_status()
            log_info("heartbeat", cid=cid, job_id=job_id)
        except Exception as exc:  # pragma: no cover - network errors
            log_error("heartbeat", cid=cid, job_id=job_id, error=str(exc))


def process_job(job: dict, session: requests.sessions.Session | None = None) -> None:
    """Claim and process a single job, handling heartbeat and status updates."""
    sess = session or requests
    base = settings.API_BASE_URL.rstrip("/")
    job_id = job.get("id")
    cid = str(uuid.uuid4())
    try:
        resp = sess.post(
            f"{base}/api/render-jobs/{job_id}/claim",
            json={"lease_seconds": settings.LEASE_SECONDS},
            timeout=30,
            headers=_headers(),
        )
        if resp.status_code in (409, 410):
            log_error("claim", cid=cid, job_id=job_id, status=resp.status_code)
            return
        resp.raise_for_status()
        log_info("claim", cid=cid, job_id=job_id)

        stop = threading.Event()
        lost = [False]
        hb_thread = threading.Thread(
            target=_heartbeat_loop,
            args=(job_id, cid, stop, lost, session),
            daemon=True,
        )
        hb_thread.start()

        worker = threading.Thread(target=render_job, args=(job,))
        worker.start()
        worker.join(timeout=settings.JOB_TIMEOUT_SEC)
        stop.set()
        hb_thread.join()

        if worker.is_alive():
            log_error("error", cid=cid, job_id=job_id, error="timeout")
            sess.post(
                f"{base}/api/render-jobs/{job_id}/status",
                json={"status": "errored", "error_message": "timeout"},
                timeout=30,
                headers=_headers(),
            )
            return
        if lost[0]:
            log_error("error", cid=cid, job_id=job_id, error="lease_lost")
            sess.post(
                f"{base}/api/render-jobs/{job_id}/status",
                json={"status": "errored", "error_message": "lease_lost"},
                timeout=30,
                headers=_headers(),
            )
            return

        sess.post(
            f"{base}/api/render-jobs/{job_id}/status",
            json={"status": "rendered"},
            timeout=30,
            headers=_headers(),
        )
        log_info("done", cid=cid, job_id=job_id)
    except Exception as exc:  # pragma: no cover - unexpected errors
        log_error("error", cid=cid, job_id=job_id, error=str(exc))
        try:
            sess.post(
                f"{base}/api/render-jobs/{job_id}/status",
                json={"status": "errored", "error_message": str(exc)},
                timeout=30,
                headers=_headers(),
            )
        finally:
            pass


def run() -> None:  # pragma: no cover - continuous loop
    """Continuously poll for jobs and process them respecting concurrency."""
    log_info("start", cid="poller")
    backoff = backoff_schedule(settings.POLL_INTERVAL_MS, factor=1.0)
    with ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT) as pool:
        running: dict[int, threading.Future] = {}
        while True:
            jobs = poll_jobs()
            for job in jobs:
                job_id = job.get("id")
                if job_id in running or len(running) >= settings.MAX_CONCURRENT:
                    continue
                future = pool.submit(process_job, job)
                running[job_id] = future
                future.add_done_callback(lambda _f, jid=job_id: running.pop(jid, None))
            time.sleep(next(backoff))


__all__ = [
    "backoff_schedule",
    "poll_jobs",
    "process_job",
    "render_job",
    "run",
]

