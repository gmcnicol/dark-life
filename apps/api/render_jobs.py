"""Worker-facing render job API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Field, SQLModel, Session, select

from shared.workflow import JobStatus, ReleaseStatus, StoryStatus, can_transition_job

from .db import get_session
from .models import (
    Compilation,
    Job,
    JobRead,
    Release,
    RenderArtifact,
    Story,
)
from .pipeline import release_for_artifact

router = APIRouter(prefix="/render-jobs", tags=["render-jobs"])

DEFAULT_LEASE_SECONDS = 180


class ClaimRequest(SQLModel):
    lease_seconds: int = DEFAULT_LEASE_SECONDS


class RenderJobStatusUpdate(SQLModel):
    status: str
    artifact_path: str | None = None
    subtitle_path: str | None = None
    waveform_path: str | None = None
    bytes: int | None = None
    duration_ms: int | None = None
    error_class: str | None = None
    error_message: str | None = None
    stderr_snippet: str | None = None
    details: dict | None = Field(default=None, alias="metadata")


@router.get("/", response_model=list[JobRead])
def list_render_jobs(
    status: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> list[Job]:
    query = select(Job).where(Job.kind.ilike("render_%"))
    if status:
        query = query.where(Job.status == status)
    query = query.order_by(Job.id).limit(limit)
    return session.exec(query).all()


@router.post("/{job_id}/claim")
def claim_render_job(
    job_id: int,
    request: ClaimRequest,
    session: Session = Depends(get_session),
) -> dict:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.QUEUED.value:
        raise HTTPException(status_code=409, detail="Invalid state")
    job.status = JobStatus.CLAIMED.value
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.lease_seconds)
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"lease_expires_at": job.lease_expires_at}


@router.post("/{job_id}/heartbeat")
def heartbeat_render_job(job_id: int, session: Session = Depends(get_session)) -> dict:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in {JobStatus.CLAIMED.value, JobStatus.RENDERING.value}:
        raise HTTPException(status_code=409, detail="Invalid state")
    if job.lease_expires_at and job.lease_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Lease expired")
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=DEFAULT_LEASE_SECONDS)
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"lease_expires_at": job.lease_expires_at}


def _upsert_artifact(job: Job, update: RenderJobStatusUpdate, session: Session) -> RenderArtifact | None:
    if not update.artifact_path:
        return None
    artifact = session.exec(
        select(RenderArtifact).where(RenderArtifact.job_id == job.id)
    ).first()
    metadata = update.details or {}
    if not artifact:
        artifact = RenderArtifact(
            job_id=job.id,
            story_id=job.story_id or 0,
            story_part_id=job.story_part_id,
            compilation_id=job.compilation_id,
            variant=job.variant,
            video_path=update.artifact_path,
            subtitle_path=update.subtitle_path,
            waveform_path=update.waveform_path,
            bytes=update.bytes,
            duration_ms=update.duration_ms,
            details=metadata,
        )
    else:
        artifact.video_path = update.artifact_path
        artifact.subtitle_path = update.subtitle_path
        artifact.waveform_path = update.waveform_path
        artifact.bytes = update.bytes
        artifact.duration_ms = update.duration_ms
        artifact.details = metadata
    session.add(artifact)
    session.flush()
    return artifact


@router.post("/{job_id}/status", response_model=JobRead)
def update_render_job_status(
    job_id: int,
    update: RenderJobStatusUpdate,
    session: Session = Depends(get_session),
) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if update.status != job.status and not can_transition_job(job.status, update.status):
        raise HTTPException(status_code=409, detail="Invalid state transition")

    job.status = update.status
    job.error_class = update.error_class
    job.error_message = update.error_message
    job.stderr_snippet = update.stderr_snippet
    if update.details or update.artifact_path:
        job.result = {
            **(job.result or {}),
            **(update.details or {}),
        }
        if update.artifact_path is not None:
            job.result["artifact_path"] = update.artifact_path
        if update.subtitle_path is not None:
            job.result["subtitle_path"] = update.subtitle_path
        if update.bytes is not None:
            job.result["bytes"] = update.bytes
        if update.duration_ms is not None:
            job.result["duration_ms"] = update.duration_ms

    artifact = _upsert_artifact(job, update, session)
    if artifact and update.status == JobStatus.RENDERED.value:
        story = session.get(Story, job.story_id) if job.story_id else None
        if story:
            story.status = StoryStatus.RENDERED.value
            session.add(story)
        for release in release_for_artifact(
            session,
            story_id=job.story_id or 0,
            story_part_id=job.story_part_id,
            compilation_id=job.compilation_id,
        ):
            release.render_artifact_id = artifact.id
            release.status = ReleaseStatus.READY.value
            session.add(release)
        if job.compilation_id:
            compilation = session.get(Compilation, job.compilation_id)
            if compilation:
                compilation.render_artifact_id = artifact.id
                compilation.status = StoryStatus.RENDERED.value
                session.add(compilation)
        job.status = JobStatus.PUBLISH_READY.value
        if story:
            story.status = StoryStatus.PUBLISH_READY.value
            session.add(story)

    session.add(job)
    session.commit()
    session.refresh(job)
    return job


__all__ = ["router"]
