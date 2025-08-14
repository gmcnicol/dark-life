"""API router for render jobs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import SQLModel, Session, select

from .db import get_session
from .models import Job

LEASE_SECONDS = 180

router = APIRouter(prefix="/render-jobs", tags=["render-jobs"])


@router.get("/", response_model=list[Job])
def list_render_jobs(
    status: Optional[str] = None,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> list[Job]:
    query = select(Job).where(Job.kind == "render_part")
    if status:
        query = query.where(Job.status == status)
    query = query.order_by(Job.id).limit(limit)
    return session.exec(query).all()


@router.post("/{job_id}/claim")
def claim_render_job(job_id: int, session: Session = Depends(get_session)) -> dict:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "queued":
        raise HTTPException(status_code=409, detail="Invalid state")
    job.status = "claimed"
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=LEASE_SECONDS)
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"lease_expires_at": job.lease_expires_at}


@router.post("/{job_id}/heartbeat")
def heartbeat_render_job(job_id: int, session: Session = Depends(get_session)) -> dict:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in {"claimed", "rendering"}:
        raise HTTPException(status_code=409, detail="Invalid state")
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=LEASE_SECONDS)
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"lease_expires_at": job.lease_expires_at}


class RenderJobStatusUpdate(SQLModel):
    status: str
    artifact_path: str | None = None
    bytes: int | None = None
    duration_ms: int | None = None
    error_class: str | None = None
    error_message: str | None = None
    stderr_snippet: str | None = None


@router.post("/{job_id}/status", response_model=Job)
def update_render_job_status(
    job_id: int,
    update: RenderJobStatusUpdate,
    session: Session = Depends(get_session),
) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    valid_next = {
        "queued": {"claimed"},
        "claimed": {"rendering"},
        "rendering": {"rendered", "errored"},
    }
    if update.status not in valid_next.get(job.status, set()):
        raise HTTPException(status_code=409, detail="Invalid state transition")
    job.status = update.status
    if update.artifact_path or update.bytes is not None or update.duration_ms is not None:
        job.result = job.result or {}
        if update.artifact_path is not None:
            job.result["artifact_path"] = update.artifact_path
        if update.bytes is not None:
            job.result["bytes"] = update.bytes
        if update.duration_ms is not None:
            job.result["duration_ms"] = update.duration_ms
    if update.error_class is not None:
        job.error_class = update.error_class
    if update.error_message is not None:
        job.error_message = update.error_message
    if update.stderr_snippet is not None:
        job.stderr_snippet = update.stderr_snippet
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


__all__ = ["router"]
