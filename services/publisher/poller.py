"""Publisher job poller interacting with the Dark Life API."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from shared.config import settings
from shared.logging import log_error, log_info
from shared.workflow import PublishJobStatus

from .api_client import PublishApiClient, auth_headers
from .pipeline import PublishPipelineError, publish_release


HEARTBEAT_FILE = Path(settings.TMP_DIR) / "publisher_heartbeat"


def _validate_runtime() -> None:
    if not settings.API_BASE_URL:
        raise RuntimeError("API_BASE_URL is required")
    Path(settings.TMP_DIR).mkdir(parents=True, exist_ok=True)


def poll_jobs(session: requests.sessions.Session | None = None) -> list[dict]:
    client = PublishApiClient(session or requests)
    jobs = client.list_jobs(status=PublishJobStatus.QUEUED.value, limit=settings.PUBLISH_MAX_CONCURRENT)
    log_info("poll", cid="publisher-poll", count=len(jobs))
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
                f"{base}/publish-jobs/{job_id}/heartbeat",
                timeout=30,
                headers=auth_headers(),
            )
            if resp.status_code in (409, 410):
                lost[0] = True
                stop.set()
                log_error("heartbeat", cid=cid, publish_job_id=job_id, status=resp.status_code)
                return
            resp.raise_for_status()
            log_info("heartbeat", cid=cid, publish_job_id=job_id)
        except Exception as exc:
            log_error("heartbeat", cid=cid, publish_job_id=job_id, error=str(exc))


def publish_job(job: dict, session: requests.sessions.Session | None = None) -> dict[str, object]:
    client = PublishApiClient(session or requests)
    context = client.get_context(int(job["id"]))
    release = context["release"]
    log_info(
        "context",
        publish_job_id=job["id"],
        release_id=release["id"],
        story_id=release["story_id"],
        platform=release["platform"],
    )
    return publish_release(context, session=session)


def process_job(job: dict, session: requests.sessions.Session | None = None) -> None:
    sess = session or requests
    client = PublishApiClient(sess)
    base = settings.API_BASE_URL.rstrip("/")
    job_id = int(job["id"])
    cid = job.get("correlation_id") or str(uuid.uuid4())
    try:
        claim_response = sess.post(
            f"{base}/publish-jobs/{job_id}/claim",
            json={"lease_seconds": settings.PUBLISH_LEASE_SECONDS},
            timeout=30,
            headers=auth_headers(),
        )
        if claim_response.status_code in (409, 410):
            log_error("claim", cid=cid, publish_job_id=job_id, status=claim_response.status_code)
            return
        claim_response.raise_for_status()
        log_info("claim", cid=cid, publish_job_id=job_id)
        client.set_status(job_id, {"status": PublishJobStatus.PUBLISHING.value})

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

        def _run_publish() -> None:
            try:
                result_holder.update(publish_job(job, session=session))
            except Exception as exc:
                error_holder.append(exc)

        worker = threading.Thread(target=_run_publish, daemon=True)
        worker.start()
        worker.join(timeout=settings.JOB_TIMEOUT_SEC)
        stop.set()
        hb_thread.join()

        if worker.is_alive():
            client.set_status(
                job_id,
                {
                    "status": PublishJobStatus.ERRORED.value,
                    "error_message": "timeout",
                    "retryable": True,
                },
            )
            return
        if lost[0]:
            client.set_status(
                job_id,
                {
                    "status": PublishJobStatus.ERRORED.value,
                    "error_message": "lease_lost",
                    "retryable": True,
                },
            )
            return
        if error_holder:
            exc = error_holder[0]
            payload = {
                "status": PublishJobStatus.ERRORED.value,
                "error_class": exc.__class__.__name__,
                "error_message": str(exc),
            }
            if isinstance(exc, PublishPipelineError):
                payload["retryable"] = exc.retryable
                if exc.stderr:
                    payload["stderr_snippet"] = exc.stderr
            log_error("error", cid=cid, publish_job_id=job_id, error=str(exc))
            client.set_status(job_id, payload)
            return

        metadata = result_holder.pop("metadata", None)
        payload = {"status": PublishJobStatus.PUBLISHED.value, **result_holder}
        if metadata is not None:
            payload["metadata"] = metadata
        client.set_status(job_id, payload)
        log_info("done", cid=cid, publish_job_id=job_id)
    except Exception as exc:
        log_error("error", cid=cid, publish_job_id=job_id, error=str(exc))
        try:
            client.set_status(
                job_id,
                {
                    "status": PublishJobStatus.ERRORED.value,
                    "error_class": exc.__class__.__name__,
                    "error_message": str(exc),
                    "retryable": False,
                },
            )
        except Exception:
            pass


def run() -> None:  # pragma: no cover - continuous loop
    _validate_runtime()
    log_info("start", cid="publisher")
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_FILE.touch()
    with ThreadPoolExecutor(max_workers=settings.PUBLISH_MAX_CONCURRENT) as pool:
        running: dict[int, object] = {}
        while True:
            HEARTBEAT_FILE.touch()
            try:
                jobs = poll_jobs()
            except Exception as exc:
                log_error("poll", error=str(exc))
                time.sleep(settings.PUBLISH_POLL_INTERVAL_SEC)
                continue
            for job in jobs:
                job_id = int(job["id"])
                if job_id in running or len(running) >= settings.PUBLISH_MAX_CONCURRENT:
                    continue
                future = pool.submit(process_job, job)
                running[job_id] = future
                future.add_done_callback(lambda _f, jid=job_id: running.pop(jid, None))
            time.sleep(settings.PUBLISH_POLL_INTERVAL_SEC)


__all__ = ["poll_jobs", "process_job", "publish_job", "run"]


if __name__ == "__main__":  # pragma: no cover
    run()
