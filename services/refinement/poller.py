"""Refinement job poller interacting with the Dark Life API."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from apps.api.models import Story, StoryConcept
from apps.api.refinement import OpenAIRefinementError, extract_concept_payload, generate_candidate_payloads
from shared.config import settings
from shared.logging import log_error, log_info
from shared.workflow import JobStatus

from .api_client import RefinementApiClient, auth_headers

HEARTBEAT_FILE = Path(settings.TMP_DIR) / "refinement_heartbeat"


def _validate_runtime() -> None:
    if not settings.API_BASE_URL:
        raise RuntimeError("API_BASE_URL is required")
    Path(settings.TMP_DIR).mkdir(parents=True, exist_ok=True)


def poll_jobs(session: requests.sessions.Session | None = None) -> list[dict]:
    client = RefinementApiClient(session or requests)
    jobs = client.list_jobs(status=JobStatus.QUEUED.value, limit=settings.REFINEMENT_MAX_CONCURRENT)
    log_info("poll", cid="refinement-poll", count=len(jobs))
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
                f"{base}/refinement-jobs/{job_id}/heartbeat",
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


def _story_from_context(context: dict[str, object]) -> Story:
    return Story.model_validate(context["story"])


def _concept_from_context(context: dict[str, object]) -> StoryConcept | None:
    concept = context.get("concept")
    if not concept:
        return None
    return StoryConcept.model_validate(concept)


def run_refinement_job(job: dict, session: requests.sessions.Session | None = None) -> dict[str, object]:
    client = RefinementApiClient(session or requests)
    context = client.get_context(int(job["id"]))
    story = _story_from_context(context)
    kind = job["kind"]
    if kind == "refine_extract_concept":
        concept, retry_metadata = extract_concept_payload(story, include_retry_metadata=True)
        return {"metadata": {"concept": concept, **retry_metadata}}
    if kind == "refine_generate_batch":
        batch = context["batch"]
        concept = _concept_from_context(context)
        candidates, retry_metadata = generate_candidate_payloads(
            story,
            concept=concept,
            candidate_count=int(batch.get("candidate_count") or settings.REFINEMENT_DEFAULT_BATCH_SIZE),
            include_retry_metadata=True,
        )
        return {"metadata": {"candidates": candidates, **retry_metadata}}
    return {"metadata": {}}


def process_job(job: dict, session: requests.sessions.Session | None = None) -> None:
    sess = session or requests
    client = RefinementApiClient(sess)
    base = settings.API_BASE_URL.rstrip("/")
    job_id = int(job["id"])
    cid = job.get("correlation_id") or str(uuid.uuid4())
    try:
        claim_response = sess.post(
            f"{base}/refinement-jobs/{job_id}/claim",
            json={"lease_seconds": settings.REFINEMENT_LEASE_SECONDS},
            timeout=30,
            headers=auth_headers(),
        )
        if claim_response.status_code in (409, 410):
            log_error("claim", cid=cid, job_id=job_id, status=claim_response.status_code)
            return
        claim_response.raise_for_status()
        client.set_status(job_id, {"status": JobStatus.RENDERING.value})

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

        def _run_job() -> None:
            try:
                result_holder.update(run_refinement_job(job, session=session))
            except Exception as exc:
                error_holder.append(exc)

        worker = threading.Thread(target=_run_job, daemon=True)
        worker.start()
        worker.join(timeout=settings.JOB_TIMEOUT_SEC)
        stop.set()
        hb_thread.join()

        if worker.is_alive():
            client.set_status(job_id, {"status": JobStatus.ERRORED.value, "error_message": "timeout"})
            return
        if lost[0]:
            client.set_status(job_id, {"status": JobStatus.ERRORED.value, "error_message": "lease_lost"})
            return
        if error_holder:
            exc = error_holder[0]
            log_error("error", cid=cid, job_id=job_id, error=str(exc))
            payload = {
                "status": JobStatus.ERRORED.value,
                "error_class": exc.__class__.__name__,
                "error_message": str(exc),
            }
            if isinstance(exc, OpenAIRefinementError):
                payload["retryable"] = exc.retryable
                payload["metadata"] = {
                    "attempt_count": exc.attempt_count,
                    "last_error_class": exc.last_error_class or exc.__class__.__name__,
                    "last_error_message": exc.last_error_message or str(exc),
                }
                if exc.response_summary:
                    payload["stderr_snippet"] = exc.response_summary
            client.set_status(
                job_id,
                payload,
            )
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


def run() -> None:  # pragma: no cover - continuous loop
    _validate_runtime()
    log_info("start", cid="refinement")
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_FILE.touch()
    with ThreadPoolExecutor(max_workers=settings.REFINEMENT_MAX_CONCURRENT) as pool:
        running: dict[int, object] = {}
        while True:
            HEARTBEAT_FILE.touch()
            try:
                jobs = poll_jobs()
            except Exception as exc:
                log_error("poll", error=str(exc))
                time.sleep(settings.REFINEMENT_POLL_INTERVAL_SEC)
                continue
            for job in jobs:
                job_id = int(job["id"])
                if job_id in running or len(running) >= settings.REFINEMENT_MAX_CONCURRENT:
                    continue
                future = pool.submit(process_job, job)
                running[job_id] = future
                future.add_done_callback(lambda _f, jid=job_id: running.pop(jid, None))
            time.sleep(settings.REFINEMENT_POLL_INTERVAL_SEC)


__all__ = ["poll_jobs", "process_job", "run", "run_refinement_job"]


if __name__ == "__main__":  # pragma: no cover
    run()
