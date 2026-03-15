"""Job APIs for operator views."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from .db import get_session
from .models import Job, JobRead, JobUpdate

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(
    story_id: int | None = None,
    story_part_id: int | None = None,
    compilation_id: int | None = None,
    kind: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
) -> list[Job]:
    query = select(Job)
    if story_id is not None:
        query = query.where(Job.story_id == story_id)
    if story_part_id is not None:
        query = query.where(Job.story_part_id == story_part_id)
    if compilation_id is not None:
        query = query.where(Job.compilation_id == compilation_id)
    if kind:
        query = query.where(Job.kind == kind)
    if status:
        query = query.where(Job.status == status)
    query = query.order_by(Job.id.desc())
    return session.exec(query).all()


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int, session: Session = Depends(get_session)) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/jobs/{job_id}", response_model=JobRead)
def update_job(
    job_id: int,
    update: JobUpdate,
    session: Session = Depends(get_session),
) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if update.status is not None:
        job.status = update.status
    if update.result is not None:
        job.result = update.result
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


__all__ = ["router"]
