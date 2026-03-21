"""Worker-facing publish job API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Session, select

from shared.config import settings
from shared.workflow import (
    PublishApprovalStatus,
    PublishJobStatus,
    ReleaseStatus,
    can_transition_publish_job,
)

from .db import get_session
from .models import PublishJob, PublishJobRead, Release, RenderArtifact, Story
from .publishing import maybe_mark_story_published, release_read, resolve_release_artifact


router = APIRouter(prefix="/publish-jobs", tags=["publish-jobs"])

DEFAULT_LEASE_SECONDS = 180


class ClaimRequest(SQLModel):
    lease_seconds: int = DEFAULT_LEASE_SECONDS


class PublishJobStatusUpdate(BaseModel):
    status: str
    platform_video_id: str | None = None
    error_class: str | None = None
    error_message: str | None = None
    stderr_snippet: str | None = None
    retryable: bool = False
    release_status_override: str | None = None
    metadata: dict | None = None


def require_worker_token(authorization: str | None = Header(default=None)) -> None:
    expected = settings.API_AUTH_TOKEN
    if not expected or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    if token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _job_due(job: PublishJob) -> bool:
    return not job.not_before or job.not_before <= datetime.now(timezone.utc)


def _assemble_publish_context(job: PublishJob, session: Session) -> dict[str, Any]:
    release = session.get(Release, job.release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    story = session.get(Story, release.story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    artifact = resolve_release_artifact(session, release)
    if not artifact:
        raise HTTPException(status_code=404, detail="Render artifact not found")
    return {
        "publish_job": PublishJobRead.model_validate(job).model_dump(),
        "release": release_read(session, release).model_dump(),
        "story": story.model_dump(),
        "artifact": artifact.model_dump(),
    }


@router.get("/", response_model=list[PublishJobRead])
def list_publish_jobs(
    status: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> list[PublishJob]:
    query = select(PublishJob)
    if status:
        query = query.where(PublishJob.status == status)
    query = query.order_by(PublishJob.id).limit(limit)
    jobs = session.exec(query).all()
    if status == PublishJobStatus.QUEUED.value:
        return [job for job in jobs if _job_due(job)]
    return jobs


@router.post("/{job_id}/claim")
def claim_publish_job(
    job_id: int,
    request: ClaimRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> dict[str, Any]:
    job = session.get(PublishJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Publish job not found")
    if job.status != PublishJobStatus.QUEUED.value:
        raise HTTPException(status_code=409, detail="Invalid state")
    if not _job_due(job):
        raise HTTPException(status_code=409, detail="Publish job is not due")
    job.status = PublishJobStatus.CLAIMED.value
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.lease_seconds)
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"lease_expires_at": job.lease_expires_at}


@router.post("/{job_id}/heartbeat")
def heartbeat_publish_job(
    job_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> dict[str, Any]:
    job = session.get(PublishJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Publish job not found")
    if job.status not in {PublishJobStatus.CLAIMED.value, PublishJobStatus.PUBLISHING.value}:
        raise HTTPException(status_code=409, detail="Invalid state")
    if job.lease_expires_at and job.lease_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Lease expired")
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=DEFAULT_LEASE_SECONDS)
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"lease_expires_at": job.lease_expires_at}


@router.get("/{job_id}/context")
def get_publish_job_context(
    job_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> dict[str, Any]:
    job = session.get(PublishJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Publish job not found")
    return _assemble_publish_context(job, session)


@router.post("/{job_id}/status", response_model=PublishJobRead)
def update_publish_job_status(
    job_id: int,
    update: PublishJobStatusUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> PublishJob:
    job = session.get(PublishJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Publish job not found")
    if update.status != job.status and not can_transition_publish_job(job.status, update.status):
        raise HTTPException(status_code=409, detail="Invalid state transition")
    release = session.get(Release, job.release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")

    job.status = update.status
    job.error_class = update.error_class
    job.error_message = update.error_message
    job.stderr_snippet = update.stderr_snippet
    if update.metadata:
        job.result = {**(job.result or {}), **update.metadata}

    if update.status == PublishJobStatus.PUBLISHING.value:
        release.status = ReleaseStatus.PUBLISHING.value
        release.publish_status = ReleaseStatus.PUBLISHING.value
    elif update.status == PublishJobStatus.PUBLISHED.value:
        override = update.release_status_override
        release.platform_video_id = update.platform_video_id or release.platform_video_id
        release.provider_metadata = {**(release.provider_metadata or {}), **(update.metadata or {})} if update.metadata else release.provider_metadata
        release.last_error = None
        if override == ReleaseStatus.MANUAL_HANDOFF.value:
            release.status = ReleaseStatus.MANUAL_HANDOFF.value
            release.publish_status = ReleaseStatus.MANUAL_HANDOFF.value
        else:
            release.status = ReleaseStatus.PUBLISHED.value
            release.publish_status = ReleaseStatus.PUBLISHED.value
            release.published_at = datetime.now(timezone.utc)
            maybe_mark_story_published(session, release.story_id)
    elif update.status == PublishJobStatus.ERRORED.value:
        job.attempts += 1
        release.attempt_count = job.attempts
        release.last_error = update.error_message
        release.provider_metadata = {**(release.provider_metadata or {}), **(update.metadata or {})} if update.metadata else release.provider_metadata
        if update.retryable and job.attempts < settings.PUBLISH_RETRY_LIMIT:
            job.status = PublishJobStatus.QUEUED.value
            job.lease_expires_at = None
            release.status = ReleaseStatus.SCHEDULED.value if release.publish_at and release.publish_at > datetime.now(timezone.utc) else ReleaseStatus.APPROVED.value
            release.publish_status = release.status
        else:
            release.status = ReleaseStatus.ERRORED.value
            release.publish_status = ReleaseStatus.ERRORED.value
    release.approval_status = release.approval_status or PublishApprovalStatus.PENDING.value

    session.add(job)
    session.add(release)
    session.commit()
    session.refresh(job)
    return job


__all__ = ["router"]
