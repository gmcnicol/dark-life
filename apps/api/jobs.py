"""Jobs API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from .db import get_session
from .models import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", response_model=list[Job])
def list_jobs(
    story_id: int | None = None,
    kind: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
) -> list[Job]:
    """Return jobs filtered by optional criteria."""
    query = select(Job)
    if story_id is not None:
        query = query.where(Job.story_id == story_id)
    if kind:
        query = query.where(Job.kind == kind)
    if status:
        query = query.where(Job.status == status)
    query = query.order_by(Job.id.desc())
    return session.exec(query).all()


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    """Return a job by ID."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


__all__ = ["router"]
